import datetime
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.bookings import (
    BookingConflictError,
    BookingValidationError,
    create_booking,
    load_bookings,
    next_available_dates,
    save_all_bookings,
    csv_lock,
)
from app.config import (
    CLINIC_INFO_PATH,
    BOOKINGS_CSV_PATH,
    get_clinic_details,
    get_clinic_info_text,
    DAILY_CAPACITY,
)


def get_clinic_info(topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Reads and extracts official clinic facts from data/clinic_info.md.
    Topics include: 'services', 'hours', 'location', 'preparation', 'appointments', 'emergencies', or 'all'.
    """
    text = get_clinic_info_text()
    details = get_clinic_details()

    services_text = (
        "We offer the following primary care services:\n"
        "• General check-ups: routine visits and health reviews.\n"
        "• Vaccinations: seasonal and travel vaccines.\n"
        "• Ongoing care: follow-ups for long-term conditions."
    )

    hours_text = f"Opening Hours: {details['hours']}. Closed Saturday and Sunday."
    location_text = f"Location: {details['address']}. Phone: {details['phone']}."
    preparation_text = (
        "Preparing for your visit:\n"
        "• Bring a photo ID, insurance card, and a list of current medications.\n"
        "• Arrive 10 minutes early to fill out forms.\n"
        "• Write down your questions beforehand."
    )
    appointments_text = (
        f"Appointments: Requests are sent to the front desk, which contacts the patient to confirm the time. "
        f"Daily capacity is {DAILY_CAPACITY} appointments per weekday."
    )
    emergency_text = f"Emergencies: Call {details['emergency_number']} immediately or visit the nearest emergency department."

    t = (topic or "").lower().strip()
    if "service" in t:
        return {"topic": "Services", "content": services_text, "source": "Services"}
    elif "hour" in t or "open" in t or "time" in t:
        return {"topic": "Hours", "content": hours_text, "source": "Hours"}
    elif "location" in t or "address" in t or "phone" in t or "contact" in t:
        return {"topic": "Location & Contact", "content": location_text, "source": "Location & Contact"}
    elif "prep" in t or "bring" in t or "document" in t:
        return {"topic": "Preparing for your visit", "content": preparation_text, "source": "Preparing for your visit"}
    elif "appoint" in t or "book" in t:
        return {"topic": "Appointments", "content": appointments_text, "source": "Appointments"}
    elif "emerg" in t:
        return {"topic": "Emergencies", "content": emergency_text, "source": "Emergencies"}

    # Default: return structured summary
    return {
        "topic": "All Clinic Info",
        "clinic_name": details["clinic_name"],
        "hours": hours_text,
        "services": services_text,
        "location": location_text,
        "preparation": preparation_text,
        "appointments": appointments_text,
        "source": "Clinic Information",
        "full_text": text,
    }


def check_booking_status(query: str, csv_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """
    Looks up booking status in data/bookings.csv by booking_id (e.g. B1001), phone, or patient name.
    """
    clean_q = query.strip()
    if not clean_q:
        return {"found": False, "message": "Please provide a booking ID, phone number, or patient name to check."}

    bookings = load_bookings(csv_path=csv_path)
    clean_norm_phone = re.sub(r"\D", "", clean_q)
    is_id = bool(re.match(r"^B\d+$", clean_q, re.IGNORECASE))

    matches = []
    for b in bookings:
        bid = b.get("booking_id", "").strip()
        bphone = b.get("phone", "").strip()
        bname = b.get("name", "").strip()

        if is_id and bid.lower() == clean_q.lower():
            matches.append(b)
            break
        elif clean_norm_phone and len(clean_norm_phone) >= 5 and clean_norm_phone in re.sub(r"\D", "", bphone):
            matches.append(b)
        elif clean_q.lower() in bname.lower() and len(clean_q) >= 3:
            matches.append(b)

    if not matches:
        return {
            "found": False,
            "query": clean_q,
            "message": f"No booking record found matching '{clean_q}' in our schedule.",
        }

    first = matches[0]
    return {
        "found": True,
        "booking_id": first.get("booking_id"),
        "name": first.get("name"),
        "phone": first.get("phone"),
        "preferred_date": first.get("preferred_date"),
        "reason": first.get("reason"),
        "status": first.get("status"),
        "created_at": first.get("created_at"),
        "total_matches": len(matches),
        "message": (
            f"Booking {first.get('booking_id')} for {first.get('name')} on {first.get('preferred_date')} "
            f"currently has status: {first.get('status')}."
        ),
    }


def update_booking_status(
    booking_id: str, new_status: str, csv_path: Optional[Path | str] = None
) -> Dict[str, Any]:
    """
    Updates the status of an existing appointment booking in data/bookings.csv.
    """
    clean_id = booking_id.strip()
    status_title = new_status.strip().title()
    if status_title not in ["Accepted", "Cancelled", "Pending"]:
        status_title = "Accepted"

    with csv_lock:
        bookings = load_bookings(csv_path=csv_path)
        target_idx = None
        for i, b in enumerate(bookings):
            if b.get("booking_id", "").strip().lower() == clean_id.lower():
                target_idx = i
                break

        if target_idx is None:
            return {
                "success": False,
                "booking_id": clean_id,
                "message": f"Could not find booking {clean_id} in the database to update.",
            }

        old_status = bookings[target_idx].get("status", "Accepted")
        bookings[target_idx]["status"] = status_title
        save_all_bookings(bookings, csv_path=csv_path)

        return {
            "success": True,
            "booking_id": clean_id,
            "old_status": old_status,
            "new_status": status_title,
            "name": bookings[target_idx].get("name"),
            "preferred_date": bookings[target_idx].get("preferred_date"),
            "message": f"Booking {clean_id} status has been successfully updated from {old_status} to {status_title} in bookings.csv.",
        }


def book_appointment_tool(
    name: str,
    phone: str,
    preferred_date: str,
    reason: Optional[str] = None,
    csv_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Books an appointment directly and saves it into data/bookings.csv.
    """
    try:
        booking = create_booking(
            name=name,
            phone=phone,
            preferred_date=preferred_date,
            reason=reason,
            csv_path=csv_path,
        )
        return {
            "success": True,
            "booking_id": booking["booking_id"],
            "name": booking["name"],
            "preferred_date": booking["preferred_date"],
            "status": booking["status"],
            "message": f"Appointment request {booking['booking_id']} for {booking['name']} on {booking['preferred_date']} has been confirmed and saved to our clinic schedule.",
        }
    except (BookingValidationError, BookingConflictError) as err:
        next_dates = getattr(err, "next_available_dates", [])
        return {
            "success": False,
            "error": str(err),
            "next_available_dates": next_dates,
            "message": f"Unable to book appointment: {str(err)}",
        }


def get_available_dates_tool(from_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns upcoming weekday dates with open capacity.
    """
    base_date = datetime.date.today()
    if from_date:
        try:
            base_date = datetime.date.fromisoformat(from_date.strip())
        except Exception:
            pass

    dates = next_available_dates(base_date, n=5)
    return {
        "success": True,
        "available_dates": dates,
        "message": f"Upcoming available dates: {', '.join(dates)}.",
    }
