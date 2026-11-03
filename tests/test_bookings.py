import concurrent.futures
import csv
import datetime
from pathlib import Path
import pytest
import shutil

from app.bookings import (
    BookingConflictError,
    BookingValidationError,
    count_accepted,
    create_booking,
    load_bookings,
    next_available_dates,
    sanitize_csv_field,
)
from app.config import BOOKINGS_CSV_PATH


@pytest.fixture
def temp_bookings_csv(tmp_path: Path):
    """Creates a temporary copy of data/bookings.csv for isolated testing."""
    test_csv = tmp_path / "bookings.csv"
    shutil.copyfile(BOOKINGS_CSV_PATH, test_csv)
    return test_csv


def test_accepts_valid_booking_with_next_id(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    res = create_booking(
        name="Alice Smith",
        phone="+1-555-0999",
        preferred_date="2026-11-04",
        reason="Routine health check",
        csv_path=temp_bookings_csv,
        current_date=current_date,
    )
    assert res["booking_id"] == "B1021"
    assert res["status"] == "Accepted"
    assert res["name"] == "Alice Smith"
    assert res["preferred_date"] == "2026-11-04"

    # Verify CSV has 21 rows (excluding header)
    bookings = load_bookings(csv_path=temp_bookings_csv)
    assert len(bookings) == 21
    assert bookings[-1]["booking_id"] == "B1021"


def test_rejects_weekend(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # 2026-11-07 is Saturday
    with pytest.raises(BookingValidationError, match="weekend"):
        create_booking(
            name="Bob Brown",
            phone="+1-555-0200",
            preferred_date="2026-11-07",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )
    # 2026-11-08 is Sunday
    with pytest.raises(BookingValidationError, match="weekend"):
        create_booking(
            name="Bob Brown",
            phone="+1-555-0200",
            preferred_date="2026-11-08",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_rejects_past_date(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    with pytest.raises(BookingValidationError, match="past"):
        create_booking(
            name="Charlie Day",
            phone="+1-555-0201",
            preferred_date="2026-11-02",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_rejects_more_than_60_days_ahead(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    too_far = (current_date + datetime.timedelta(days=61)).isoformat()
    with pytest.raises(BookingValidationError, match="60 days"):
        create_booking(
            name="Diana Prince",
            phone="+1-555-0202",
            preferred_date=too_far,
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_rejects_invalid_phone(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # Too short
    with pytest.raises(BookingValidationError, match="Phone"):
        create_booking(
            name="Evan Wright",
            phone="12345",
            preferred_date="2026-11-05",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )
    # Letters in phone
    with pytest.raises(BookingValidationError, match="Phone"):
        create_booking(
            name="Evan Wright",
            phone="+1-555-CALLME",
            preferred_date="2026-11-05",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_rejects_duplicate_phone_and_date(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # Aisha Khan already has an accepted booking on 2026-11-04 with phone +1-555-0101
    with pytest.raises(BookingConflictError, match="already exists"):
        create_booking(
            name="Aisha Duplicate",
            phone="+1-555-0101",
            preferred_date="2026-11-04",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_rejects_full_day_and_returns_next_available_dates(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # 2026-11-10 is full with 8 accepted bookings
    with pytest.raises(BookingConflictError) as exc_info:
        create_booking(
            name="George Clooney",
            phone="+1-555-0333",
            preferred_date="2026-11-10",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )
    err = exc_info.value
    assert "full capacity" in err.detail
    assert len(err.next_available_dates) == 3
    assert err.next_available_dates == ["2026-11-11", "2026-11-12", "2026-11-13"]


def test_cancelled_rows_do_not_count_toward_capacity(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # 2026-11-13 has B1016 (Accepted) and B1017 (Cancelled). So accepted count is 1.
    assert count_accepted("2026-11-13", csv_path=temp_bookings_csv) == 1

    # We should be able to add 7 more bookings on 2026-11-13
    for i in range(7):
        create_booking(
            name=f"Patient {i}",
            phone=f"+1-555-07{i:02d}",
            preferred_date="2026-11-13",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )
    assert count_accepted("2026-11-13", csv_path=temp_bookings_csv) == 8

    # The 9th booking (8 accepted + 1 cancelled) must fail capacity
    with pytest.raises(BookingConflictError, match="full capacity"):
        create_booking(
            name="Overflow Patient",
            phone="+1-555-0990",
            preferred_date="2026-11-13",
            csv_path=temp_bookings_csv,
            current_date=current_date,
        )


def test_csv_injection_sanitization(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    malicious_name = "=SUM(A1:A10)\nNew line"
    malicious_reason = "@HYPERLINK('http://malicious.com','Click')\r\nExploit"

    res = create_booking(
        name=malicious_name,
        phone="+1-555-0888",
        preferred_date="2026-11-05",
        reason=malicious_reason,
        csv_path=temp_bookings_csv,
        current_date=current_date,
    )

    # Name and reason should be sanitized with leading quote and stripped newlines
    assert res["name"].startswith("'=SUM")
    assert "\n" not in res["name"]
    assert res["reason"].startswith("'@HYPERLINK")
    assert "\n" not in res["reason"]
    assert "\r" not in res["reason"]


def test_concurrent_bookings_thread_safety(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # 2026-11-04 already has 2 accepted bookings (B1001, B1002).
    # Daily capacity is 8, so exactly 6 remaining slots are available.
    target_date = "2026-11-04"
    num_threads = 12
    results = []
    errors = []

    def attempt_booking(index):
        try:
            r = create_booking(
                name=f"Concurrent Patient {index}",
                phone=f"+1-555-99{index:02d}",
                preferred_date=target_date,
                csv_path=temp_bookings_csv,
                current_date=current_date,
            )
            return ("SUCCESS", r)
        except Exception as e:
            return ("ERROR", e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_booking, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            status, res = f.result()
            if status == "SUCCESS":
                results.append(res)
            else:
                errors.append(res)

    # Exactly 6 must succeed, bringing total accepted on 2026-11-04 to 8
    assert len(results) == 6
    assert len(errors) == 6
    for err in errors:
        assert isinstance(err, BookingConflictError)
        assert "full capacity" in err.detail

    # All generated IDs must be unique
    assigned_ids = [r["booking_id"] for r in results]
    assert len(assigned_ids) == len(set(assigned_ids))

    # Accepted count on CSV must equal 8
    assert count_accepted(target_date, csv_path=temp_bookings_csv) == 8


def test_update_existing_booking(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    # Update B1001 with new status, reason, and phone
    updated = create_booking(
        booking_id="B1001",
        name="Aisha Updated",
        phone="+1-555-9999",
        preferred_date="2026-11-04",
        reason="Follow-up checkup",
        status="Pending",
        created_at="2026-11-01T09:12:00",
        csv_path=temp_bookings_csv,
        current_date=current_date,
    )
    assert updated["booking_id"] == "B1001"
    assert updated["name"] == "Aisha Updated"
    assert updated["phone"] == "+1-555-9999"
    assert updated["status"] == "Pending"
    assert updated["reason"] == "Follow-up checkup"

    # Verify CSV has persisted update
    all_rows = load_bookings(csv_path=temp_bookings_csv)
    b1001_row = next(r for r in all_rows if r["booking_id"] == "B1001")
    assert b1001_row["name"] == "Aisha Updated"
    assert b1001_row["status"] == "Pending"
    assert b1001_row["phone"] == "+1-555-9999"


def test_create_booking_with_all_columns(temp_bookings_csv):
    current_date = datetime.date(2026, 11, 3)
    res = create_booking(
        booking_id="B9999",
        name="Custom Record",
        phone="+1-555-8888",
        preferred_date="2026-11-05",
        reason="Specialist consultation",
        status="Accepted",
        created_at="2026-11-03T12:00:00",
        csv_path=temp_bookings_csv,
        current_date=current_date,
    )
    assert res["booking_id"] == "B9999"
    assert res["name"] == "Custom Record"
    assert res["phone"] == "+1-555-8888"
    assert res["preferred_date"] == "2026-11-05"
    assert res["reason"] == "Specialist consultation"
    assert res["status"] == "Accepted"
    assert res["created_at"] == "2026-11-03T12:00:00"

    all_rows = load_bookings(csv_path=temp_bookings_csv)
    b9999_row = next(r for r in all_rows if r["booking_id"] == "B9999")
    assert b9999_row["name"] == "Custom Record"

