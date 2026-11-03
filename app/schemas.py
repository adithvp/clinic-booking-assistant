from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=500)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=12)


class ChatResponse(BaseModel):
    reply: str
    intent: Literal["faq", "booking", "emergency", "medical_advice", "other"]
    source: Optional[str] = None
    booking_reason: Optional[str] = None


class BookingRequest(BaseModel):
    booking_id: Optional[str] = Field(default=None, max_length=50)
    name: str = Field(..., min_length=2, max_length=80)
    phone: str = Field(..., min_length=7, max_length=20)
    preferred_date: str
    reason: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = Field(default="Accepted", max_length=50)
    created_at: Optional[str] = Field(default=None, max_length=50)


class BookingResponse(BaseModel):
    booking_id: str
    name: str
    preferred_date: str
    message: str
    phone: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = "Accepted"
    created_at: Optional[str] = None


class BookingRejectionResponse(BaseModel):
    detail: str
    next_available_dates: list[str] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    clinic_name: str
    open_weekdays: str
    today: str
    hours: str
    address: str
    phone: str
    emergency_number: str
