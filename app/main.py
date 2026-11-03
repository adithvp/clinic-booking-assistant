import collections
import datetime
import os
import time
from pathlib import Path
from typing import Deque, Dict, List

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.bookings import (
    BookingConflictError,
    BookingValidationError,
    create_booking,
    load_bookings,
)
from app.llm import ask_assistant
from app.safety import check_emergency
from app.schemas import (
    BookingRejectionResponse,
    BookingRequest,
    BookingResponse,
    ChatRequest,
    ChatResponse,
    ConfigResponse,
)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Clinic Assistant API", version="1.0.0")

# CORS middleware for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory IP rate limiter for /api/chat: 20 requests per 60 seconds
RATE_LIMIT_WINDOW = 60.0  # seconds
RATE_LIMIT_MAX_REQUESTS = 20
ip_request_history: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)


def enforce_rate_limit(client_ip: str) -> None:
    now = time.time()
    history = ip_request_history[client_ip]
    while history and now - history[0] > RATE_LIMIT_WINDOW:
        history.popleft()
    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 20 chat requests per minute.",
        )
    history.append(now)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else {"msg": "Invalid input"}
    msg = first_error.get("msg", "Invalid input")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"{msg} at {loc}" if loc else msg},
    )


@app.get("/api/config", response_model=ConfigResponse)
def get_config():
    """Returns clinic configuration for frontend initialization."""
    details = config.get_clinic_details()
    today_str = datetime.date.today().isoformat()
    return ConfigResponse(
        clinic_name=details["clinic_name"],
        open_weekdays=config.OPEN_WEEKDAYS,
        today=today_str,
        hours=details["hours"],
        address=details["address"],
        phone=details["phone"],
        emergency_number=details["emergency_number"],
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, request: Request):
    """
    Chat endpoint for answering clinic FAQs and detecting booking intents.
    1. Checks in-memory rate limit.
    2. Runs emergency keyword detection on the latest user message.
    3. Verifies API key and delegates to LLM.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    enforce_rate_limit(client_ip)

    # Find the latest user message
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one user message is required.",
        )
    latest_user_content = user_messages[-1].content

    # Safety check (NO LLM, instant fixed response)
    emergency_resp = check_emergency(latest_user_content)
    if emergency_resp:
        return emergency_resp

    # Check OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY", config.OPENAI_API_KEY).strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured. Please set OPENAI_API_KEY in your .env file.",
        )

    try:
        return ask_assistant(payload.messages, api_key=api_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing error: {str(exc)}",
        )


@app.get("/api/bookings", response_model=List[BookingResponse])
def get_bookings_endpoint():
    """Returns all current bookings from data/bookings.csv."""
    bookings = load_bookings()
    return [
        BookingResponse(
            booking_id=b.get("booking_id", ""),
            name=b.get("name", ""),
            phone=b.get("phone", ""),
            preferred_date=b.get("preferred_date", ""),
            reason=b.get("reason", ""),
            status=b.get("status", "Accepted"),
            created_at=b.get("created_at", ""),
            message="Booking loaded",
        )
        for b in bookings
    ]


@app.post(
    "/api/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": BookingRejectionResponse},
        422: {"description": "Validation error"},
    },
)
def create_booking_endpoint(payload: BookingRequest):
    """
    Creates or updates an appointment booking.
    Accepts requests and writes/updates in data/bookings.csv.
    Returns 201 on success, 409 on duplicate/capacity rejection, 422 on validation failure.
    """
    try:
        booking = create_booking(
            name=payload.name,
            phone=payload.phone,
            preferred_date=payload.preferred_date,
            reason=payload.reason,
            booking_id=payload.booking_id,
            status=payload.status or "Accepted",
            created_at=payload.created_at,
        )
        return BookingResponse(
            booking_id=booking["booking_id"],
            name=booking["name"],
            phone=booking.get("phone"),
            preferred_date=booking["preferred_date"],
            reason=booking.get("reason"),
            status=booking.get("status", "Accepted"),
            created_at=booking.get("created_at"),
            message="Your appointment request has been accepted. The front desk will contact you to confirm the time.",
        )
    except BookingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except BookingConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": exc.detail,
                "next_available_dates": exc.next_available_dates,
            },
        )


@app.put(
    "/api/bookings/{booking_id}",
    response_model=BookingResponse,
    responses={
        409: {"model": BookingRejectionResponse},
        422: {"description": "Validation error"},
    },
)
def update_booking_endpoint(booking_id: str, payload: BookingRequest):
    """
    Updates an existing appointment booking in data/bookings.csv.
    """
    try:
        booking = create_booking(
            name=payload.name,
            phone=payload.phone,
            preferred_date=payload.preferred_date,
            reason=payload.reason,
            booking_id=booking_id,
            status=payload.status or "Accepted",
            created_at=payload.created_at,
        )
        return BookingResponse(
            booking_id=booking["booking_id"],
            name=booking["name"],
            phone=booking.get("phone"),
            preferred_date=booking["preferred_date"],
            reason=booking.get("reason"),
            status=booking.get("status", "Accepted"),
            created_at=booking.get("created_at"),
            message="Your appointment booking has been successfully updated in the schedule.",
        )
    except BookingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except BookingConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": exc.detail,
                "next_available_dates": exc.next_available_dates,
            },
        )


# Mount static frontend at root
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
