import re
from typing import Optional
from app.config import get_clinic_details
from app.schemas import ChatResponse

EMERGENCY_KEYWORDS = [
    r"\bchest pain\b",
    r"\bcan['’]?t breathe\b",
    r"\bdifficulty breathing\b",
    r"\bstroke\b",
    r"\boverdose\b",
    r"\bsuicidal\b",
    r"\bheavy bleeding\b",
    r"\bunconscious\b",
    r"\bsevere allergic reaction\b",
]

COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in EMERGENCY_KEYWORDS]


def check_emergency(message: str) -> Optional[ChatResponse]:
    """
    Checks if the user's latest message matches critical emergency keywords.
    Returns a fixed emergency ChatResponse if matched, otherwise None.
    Does NOT call OpenAI.
    """
    if not message:
        return None

    for pattern in COMPILED_PATTERNS:
        if pattern.search(message):
            emergency_num = get_clinic_details().get("emergency_number", "[emergency number]")
            reply = (
                f"This sounds like a medical emergency. Please call {emergency_num} "
                "or go to the nearest emergency room immediately. Do not use this chat."
            )
            return ChatResponse(
                reply=reply,
                intent="emergency",
                source="Emergencies",
                booking_reason=None,
            )

    return None
