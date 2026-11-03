import csv
import datetime
import os
import re
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import (
    BOOKINGS_CSV_PATH,
    DAILY_CAPACITY,
    MAX_DAYS_AHEAD,
)

csv_lock = threading.Lock()

PHONE_REGEX = re.compile(r"^[0-9+\-()\s]{7,20}$")


class BookingValidationError(Exception):
    """Raised when validation fails (422)."""
    pass


class BookingConflictError(Exception):
    """Raised when a duplicate or capacity conflict occurs (409)."""
    def __init__(self, detail: str, next_available_dates: Optional[List[str]] = None):
        super().__init__(detail)
        self.detail = detail
        self.next_available_dates = next_available_dates or []


def sanitize_csv_field(value: Optional[str]) -> str:
    """Sanitise text against CSV formula injection and strip newlines."""
    if not value:
        return ""
    clean = value.replace("\r", " ").replace("\n", " ").strip()
    if clean and clean[0] in ("=", "+", "-", "@"):
        clean = "'" + clean
    return clean


def sanitize_phone(phone: str) -> str:
    """Strip newlines from phone string."""
    return phone.replace("\r", " ").replace("\n", " ").strip()


def load_bookings(csv_path: Optional[Path | str] = None) -> List[Dict[str, str]]:
    """Loads all booking records from CSV."""
    target_path = Path(csv_path) if csv_path else BOOKINGS_CSV_PATH
    if not target_path.exists():
        return []
    
    with open(target_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def count_accepted(date_str: str, csv_path: Optional[Path | str] = None) -> int:
    """Counts accepted bookings for a specific date (YYYY-MM-DD)."""
    bookings = load_bookings(csv_path=csv_path)
    count = 0
    for b in bookings:
        if b.get("preferred_date") == date_str and b.get("status", "").strip().lower() == "accepted":
            count += 1
    return count


def next_available_dates(
    from_date: datetime.date,
    n: int = 3,
    csv_path: Optional[Path | str] = None,
    max_days_ahead: int = MAX_DAYS_AHEAD,
    daily_capacity: int = DAILY_CAPACITY,
) -> List[str]:
    """Finds the next n available weekday dates starting after from_date with capacity."""
    available: List[str] = []
    current = from_date + datetime.timedelta(days=1)
    limit = from_date + datetime.timedelta(days=max_days_ahead)
    
    while len(available) < n and current <= limit:
        # Check weekday (Monday=0, Sunday=6)
        if current.weekday() < 5:
            date_str = current.isoformat()
            if count_accepted(date_str, csv_path=csv_path) < daily_capacity:
                available.append(date_str)
        current += datetime.timedelta(days=1)
        
    return available


def save_all_bookings(bookings: List[Dict[str, str]], csv_path: Optional[Path | str] = None) -> None:
    """Writes all booking records to CSV."""
    target_path = Path(csv_path) if csv_path else BOOKINGS_CSV_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "booking_id",
        "name",
        "phone",
        "preferred_date",
        "reason",
        "status",
        "created_at",
    ]
    with open(target_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for b in bookings:
            writer.writerow(b)


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def create_booking(
    name: str,
    phone: str,
    preferred_date: str,
    reason: Optional[str] = None,
    booking_id: Optional[str] = None,
    status: Optional[str] = "Accepted",
    created_at: Optional[str] = None,
    csv_path: Optional[Path | str] = None,
    current_date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """
    Validates and creates or updates an appointment booking following business rules.
    Thread-safe with CSV lock.
    """
    target_path = Path(csv_path) if csv_path else BOOKINGS_CSV_PATH
    today = current_date or datetime.date.today()

    # Rule 1: Validation of input formats
    clean_name = name.strip() if name else ""
    if len(clean_name) < 2 or len(clean_name) > 80:
        raise BookingValidationError("Name must be between 2 and 80 characters.")

    clean_phone = sanitize_phone(phone)
    if not clean_phone or not PHONE_REGEX.match(clean_phone):
        raise BookingValidationError(
            "Phone must be 7 to 20 characters and contain only digits, spaces, and + - ( )."
        )
    # Ensure there are at least some actual digits
    if len(_normalize_phone(clean_phone)) < 5:
        raise BookingValidationError("Phone number must contain at least 5 digits.")

    try:
        booking_date = datetime.date.fromisoformat(preferred_date.strip())
    except (ValueError, TypeError, AttributeError):
        raise BookingValidationError("Preferred date must be a valid date in YYYY-MM-DD format.")

    clean_booking_id = booking_id.strip() if booking_id else ""
    clean_status = sanitize_csv_field(status.strip() if status else "Accepted")
    if not clean_status:
        clean_status = "Accepted"

    # Thread-safe operations for duplicate, capacity, ID assignment and appending/updating
    with csv_lock:
        bookings = load_bookings(csv_path=target_path)
        date_str = booking_date.isoformat()
        norm_phone = _normalize_phone(clean_phone)

        existing_index = None
        if clean_booking_id:
            for idx, b in enumerate(bookings):
                if b.get("booking_id", "").strip().lower() == clean_booking_id.lower():
                    existing_index = idx
                    break

        # Date constraints check
        if existing_index is not None:
            # If updating an existing booking, only validate date constraints if date changed
            existing_date_str = bookings[existing_index].get("preferred_date", "")
            if date_str != existing_date_str:
                if booking_date < today:
                    raise BookingValidationError("Preferred date cannot be in the past.")
                if booking_date > today + datetime.timedelta(days=MAX_DAYS_AHEAD):
                    raise BookingValidationError(
                        f"Preferred date cannot be more than {MAX_DAYS_AHEAD} days in advance."
                    )
                if booking_date.weekday() >= 5:
                    raise BookingValidationError(
                        "The clinic is closed on weekends. Please choose a weekday (Monday to Friday)."
                    )
        else:
            if booking_date < today:
                raise BookingValidationError("Preferred date cannot be in the past.")
            if booking_date > today + datetime.timedelta(days=MAX_DAYS_AHEAD):
                raise BookingValidationError(
                    f"Preferred date cannot be more than {MAX_DAYS_AHEAD} days in advance."
                )
            if booking_date.weekday() >= 5:
                raise BookingValidationError(
                    "The clinic is closed on weekends. Please choose a weekday (Monday to Friday)."
                )

        # Duplicate & Capacity checks (only if status is Accepted)
        if clean_status.lower() == "accepted":
            for idx, b in enumerate(bookings):
                if existing_index is not None and idx == existing_index:
                    continue
                if (
                    b.get("preferred_date") == date_str
                    and b.get("status", "").strip().lower() == "accepted"
                    and _normalize_phone(b.get("phone", "")) == norm_phone
                ):
                    raise BookingConflictError(
                        f"An accepted booking for {clean_phone} on {date_str} already exists."
                    )

            accepted_count = sum(
                1 for idx, b in enumerate(bookings)
                if (existing_index is None or idx != existing_index)
                and b.get("preferred_date") == date_str
                and b.get("status", "").strip().lower() == "accepted"
            )
            if accepted_count >= DAILY_CAPACITY:
                next_dates = next_available_dates(booking_date, n=3, csv_path=target_path)
                raise BookingConflictError(
                    f"No appointments available on {date_str}. The clinic is at full capacity ({DAILY_CAPACITY} bookings).",
                    next_available_dates=next_dates,
                )

        # Sanitize text fields against CSV formula injection
        safe_name = sanitize_csv_field(clean_name)
        safe_reason = sanitize_csv_field(reason) if reason else ""

        if existing_index is not None:
            # Update existing record
            orig_record = bookings[existing_index]
            safe_created_at = (
                sanitize_csv_field(created_at) if created_at
                else orig_record.get("created_at", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )
            updated_row = {
                "booking_id": orig_record.get("booking_id", clean_booking_id),
                "name": safe_name,
                "phone": clean_phone,
                "preferred_date": date_str,
                "reason": safe_reason,
                "status": clean_status,
                "created_at": safe_created_at,
            }
            bookings[existing_index] = updated_row
            save_all_bookings(bookings, csv_path=target_path)
            return updated_row

        # Create new record
        if clean_booking_id:
            final_booking_id = sanitize_csv_field(clean_booking_id)
        else:
            max_num = 1000
            for b in bookings:
                bid = b.get("booking_id", "")
                if bid.startswith("B"):
                    try:
                        num = int(bid[1:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            final_booking_id = f"B{max_num + 1}"

        if created_at:
            safe_created_at = sanitize_csv_field(created_at)
        else:
            safe_created_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        new_row = {
            "booking_id": final_booking_id,
            "name": safe_name,
            "phone": clean_phone,
            "preferred_date": date_str,
            "reason": safe_reason,
            "status": clean_status,
            "created_at": safe_created_at,
        }

        # Ensure target file exists and ends with a newline before appending
        file_exists = target_path.exists()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if file_exists and target_path.stat().st_size > 0:
            with open(target_path, "rb+") as f:
                f.seek(-1, os.SEEK_END)
                last_char = f.read(1)
                if last_char not in (b"\n", b"\r"):
                    f.write(b"\n")

        with open(target_path, mode="a", encoding="utf-8", newline="") as f:
            fieldnames = [
                "booking_id",
                "name",
                "phone",
                "preferred_date",
                "reason",
                "status",
                "created_at",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists or os.path.getsize(target_path) == 0:
                writer.writeheader()
            writer.writerow(new_row)

        return new_row
