import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CLINIC_INFO_PATH = DATA_DIR / "clinic_info.md"
BOOKINGS_CSV_PATH = DATA_DIR / "bookings.csv"
LOGS_DIR = BASE_DIR / "logs"
APP_LOG_PATH = LOGS_DIR / "app.log"

DAILY_CAPACITY = 8
OPEN_WEEKDAYS = "Monday to Friday"
MAX_DAYS_AHEAD = 60

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def get_clinic_info_text() -> str:
    if CLINIC_INFO_PATH.exists():
        return CLINIC_INFO_PATH.read_text(encoding="utf-8")
    return ""


def get_clinic_details() -> dict:
    """Extract metadata from clinic_info.md with fallback defaults."""
    text = get_clinic_info_text()
    first_line = ""
    hours = "7 AM to 8 PM"
    address = "Bangalore"
    phone = "674-252-024"
    emergency_number = "8785415621"

    if text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            first_line = re.sub(r"^#+\s*", "", lines[0]).strip()
        
        hours_match = re.search(r"Monday to Friday,\s*([^.]+)\.", text, re.IGNORECASE)
        if hours_match:
            h_val = hours_match.group(1).strip()
            if h_val and h_val.lower() != "[hours]":
                hours = h_val
            
        addr_match = re.search(r"Address:\s*([^.]+)\.", text, re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip()
            
        phone_match = re.search(r"Phone:\s*([^.]+)\.", text, re.IGNORECASE)
        if phone_match:
            phone = phone_match.group(1).strip()
            
        emerg_match = re.search(r"Call\s+([^;]+);", text, re.IGNORECASE)
        if emerg_match:
            emergency_number = emerg_match.group(1).strip()

    clinic_name = os.getenv("CLINIC_NAME") or first_line or "WELL Care"
    return {
        "clinic_name": clinic_name,
        "hours": f"Monday to Friday, {hours}",
        "address": address,
        "phone": phone,
        "emergency_number": emergency_number,
    }


CLINIC_NAME = get_clinic_details()["clinic_name"]
