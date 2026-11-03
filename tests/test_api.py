import datetime
from pathlib import Path
import shutil
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.main import (
    chat_endpoint,
    create_booking_endpoint,
    enforce_rate_limit,
    get_bookings_endpoint,
    get_config,
    ip_request_history,
    update_booking_endpoint,
)
from app.config import BOOKINGS_CSV_PATH
from app.schemas import (
    BookingRequest,
    BookingResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConfigResponse,
)


@pytest.fixture
def temp_csv_path(tmp_path: Path, monkeypatch):
    """Sets up a temporary bookings CSV."""
    test_csv = tmp_path / "bookings.csv"
    shutil.copyfile(BOOKINGS_CSV_PATH, test_csv)
    monkeypatch.setattr("app.bookings.BOOKINGS_CSV_PATH", test_csv)
    monkeypatch.setattr("app.config.BOOKINGS_CSV_PATH", test_csv)
    return test_csv


def make_mock_request(client_ip="127.0.0.1"):
    req = MagicMock()
    req.client.host = client_ip
    return req


def test_get_config(temp_csv_path):
    res = get_config()
    assert isinstance(res, ConfigResponse)
    assert res.clinic_name is not None
    assert res.open_weekdays == "Monday to Friday"
    assert res.today is not None
    assert res.hours is not None
    assert res.phone is not None


def test_chat_emergency_keyword_bypasses_openai(temp_csv_path, monkeypatch):
    # Ensure OPENAI_API_KEY is unset to verify OpenAI is never invoked
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("app.config.OPENAI_API_KEY", "")

    payload = ChatRequest(
        messages=[
            ChatMessage(role="user", content="I am experiencing severe chest pain right now")
        ]
    )
    req = make_mock_request("10.0.0.1")
    res = chat_endpoint(payload, req)
    assert isinstance(res, ChatResponse)
    assert res.intent == "emergency"
    assert res.source == "Emergencies"
    assert "medical emergency" in res.reply.lower()


def test_chat_missing_api_key_returns_503(temp_csv_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("app.config.OPENAI_API_KEY", "")

    payload = ChatRequest(
        messages=[
            ChatMessage(role="user", content="What are your hours?")
        ]
    )
    req = make_mock_request("10.0.0.2")
    with pytest.raises(HTTPException) as exc_info:
        chat_endpoint(payload, req)
    assert exc_info.value.status_code == 503
    assert "OpenAI API key is not configured" in exc_info.value.detail


def test_chat_with_mocked_llm(temp_csv_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setattr("app.config.OPENAI_API_KEY", "mock-key")

    mock_resp = ChatResponse(
        reply="We provide general check-ups, vaccines, and ongoing care.",
        intent="faq",
        source="Services",
        booking_reason=None,
    )
    monkeypatch.setattr("app.main.ask_assistant", lambda messages, api_key: mock_resp)

    payload = ChatRequest(
        messages=[
            ChatMessage(role="user", content="What services do you provide?")
        ]
    )
    req = make_mock_request("10.0.0.3")
    res = chat_endpoint(payload, req)
    assert res.intent == "faq"
    assert res.source == "Services"
    assert "general check-ups" in res.reply


def test_chat_rate_limiting():
    client_ip = "192.168.1.99"
    ip_request_history[client_ip].clear()

    # 20 requests allowed
    for _ in range(20):
        enforce_rate_limit(client_ip)

    # 21st request must trigger 429
    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit(client_ip)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


def test_post_bookings_accepted_201(temp_csv_path, monkeypatch):
    monkeypatch.setattr(
        "app.bookings.datetime.date",
        type("MockDate", (datetime.date,), {"today": classmethod(lambda cls: datetime.date(2026, 11, 3))}),
    )

    payload = BookingRequest(
        name="Sarah Connor",
        phone="+1-555-4321",
        preferred_date="2026-11-05",
        reason="Vaccination check",
    )
    res = create_booking_endpoint(payload)
    assert isinstance(res, BookingResponse)
    assert res.booking_id == "B1021"
    assert res.name == "Sarah Connor"
    assert res.preferred_date == "2026-11-05"
    assert "accepted" in res.message.lower()


def test_post_bookings_duplicate_409(temp_csv_path, monkeypatch):
    monkeypatch.setattr(
        "app.bookings.datetime.date",
        type("MockDate", (datetime.date,), {"today": classmethod(lambda cls: datetime.date(2026, 11, 3))}),
    )

    payload = BookingRequest(
        name="Aisha Khan Duplicate",
        phone="+1-555-0101",
        preferred_date="2026-11-04",
    )
    res = create_booking_endpoint(payload)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 409


def test_post_bookings_capacity_full_409(temp_csv_path, monkeypatch):
    monkeypatch.setattr(
        "app.bookings.datetime.date",
        type("MockDate", (datetime.date,), {"today": classmethod(lambda cls: datetime.date(2026, 11, 3))}),
    )

    # 2026-11-10 is full
    payload = BookingRequest(
        name="John Doe",
        phone="+1-555-7777",
        preferred_date="2026-11-10",
    )
    res = create_booking_endpoint(payload)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 409


def test_post_bookings_invalid_input_422(temp_csv_path, monkeypatch):
    monkeypatch.setattr(
        "app.bookings.datetime.date",
        type("MockDate", (datetime.date,), {"today": classmethod(lambda cls: datetime.date(2026, 11, 3))}),
    )

    # Weekend date (2026-11-07)
    payload = BookingRequest(
        name="Valid Name",
        phone="+1-555-0199",
        preferred_date="2026-11-07",
    )
    with pytest.raises(HTTPException) as exc_info:
        create_booking_endpoint(payload)
    assert exc_info.value.status_code == 422


def test_get_all_bookings_endpoint(temp_csv_path):
    bookings = get_bookings_endpoint()
    assert isinstance(bookings, list)
    assert len(bookings) >= 20
    first = bookings[0]
    assert first.booking_id == "B1001"
    assert first.name == "Aisha Khan"
    assert first.phone == "+1-555-0101"
    assert first.preferred_date == "2026-11-04"
    assert first.reason == "General check-up"
    assert first.status == "Accepted"
    assert first.created_at == "2026-11-01T09:12:00"


def test_update_booking_endpoint(temp_csv_path, monkeypatch):
    monkeypatch.setattr(
        "app.bookings.datetime.date",
        type("MockDate", (datetime.date,), {"today": classmethod(lambda cls: datetime.date(2026, 11, 3))}),
    )

    payload = BookingRequest(
        name="Aisha Khan Renamed",
        phone="+1-555-0101",
        preferred_date="2026-11-04",
        reason="Updated check-up note",
        status="Cancelled",
        created_at="2026-11-01T09:12:00",
    )
    res = update_booking_endpoint("B1001", payload)
    assert isinstance(res, BookingResponse)
    assert res.booking_id == "B1001"
    assert res.name == "Aisha Khan Renamed"
    assert res.status == "Cancelled"
    assert res.reason == "Updated check-up note"

