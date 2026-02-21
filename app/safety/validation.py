"""
Validation layer for structured extraction results.

This module:
- Normalizes alternative field names into a canonical schema.
- Validates destination format based on notification type.
- Enforces minimal semantic constraints before business processing.

Acts as the final safeguard before invoking external side effects.
"""

import re
from typing import Optional


# Basic email validation pattern (intentionally simple and practical).
_EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

# Phone validation pattern allowing digits, separators and country prefixes.
_PHONE_REGEX = re.compile(
    r"^[0-9\-+\s]{6,20}$"
)

# Supported alternative keys that may represent the destination field.
_TO_KEYS = ("to", "recipient", "destination")

# Supported alternative keys that may represent the message body.
_MESSAGE_KEYS = ("message", "body", "text")

# Supported alternative keys that may represent the notification type.
_TYPE_KEYS = ("type", "channel", "method")


# Normalize incoming dictionary keys to canonical {to, message, type}.
# Returns None if mandatory fields are missing.
def _normalize_keys(data: dict) -> Optional[dict]:
    lowered = {k.lower(): v for k, v in data.items() if isinstance(k, str)}

    result = {}

    # Extract destination value.
    # to
    for key in _TO_KEYS:
        if key in lowered and isinstance(lowered[key], str):
            result["to"] = lowered[key].strip()
            break

    if not result.get("to"):
        return None

    # message (optional but default empty)
    for key in _MESSAGE_KEYS:
        if key in lowered:
            val = lowered[key]
            result["message"] = str(val).strip() if val else ""
            break
    result.setdefault("message", "")

    # type
    for key in _TYPE_KEYS:
        if key in lowered and isinstance(lowered[key], str):
            result["type"] = lowered[key].strip().lower()
            break

    if "type" not in result:
        return None

    return result


# Validate email format using predefined regex.
def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_REGEX.match(value))


# Validate phone format using predefined regex.
def _is_valid_phone(value: str) -> bool:
    return bool(_PHONE_REGEX.match(value))


# Validate destination according to declared notification type.
def _validate_destination(to: str, type_: str) -> bool:
    if type_ == "email":
        return _is_valid_email(to)
    if type_ == "sms":
        return _is_valid_phone(to)
    return False


# Public validation entry point.
# Ensures structural correctness and semantic consistency.
def validate_extraction(data: dict) -> Optional[dict]:
    """
    Validate and normalize extraction result.
    Returns canonical dict or None if invalid.
    """
    normalized = _normalize_keys(data)
    if not normalized:
        return None

    to = normalized["to"]
    type_ = normalized["type"]
    message = normalized["message"]

    if type_ not in ("email", "sms"):
        return None

    if not _validate_destination(to, type_):
        return None

    # Minimal message length
    if not message or len(message.strip()) == 0:
        return None

    return {
        "to": to,
        "message": message,
        "type": type_,
    }