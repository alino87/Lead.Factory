from typing import Optional, Tuple

from app.models.lead import LeadRequest

MIN_TEXT_LENGTH = 20


def validate(lead: LeadRequest) -> Tuple[bool, Optional[str]]:
    """
    Run basic pre-flight checks on the raw input text before sending to Claude.
    Returns (is_valid, skip_reason).
    """
    text = lead.text.strip() if lead.text else ""

    if len(text) < MIN_TEXT_LENGTH:
        return False, f"insufficient_data: text too short ({len(text)} chars, min {MIN_TEXT_LENGTH})"

    return True, None
