"""Input validators for user-submitted text (name / phone / address)."""
from __future__ import annotations

import re

# Letters from Latin, Cyrillic (incl. Uzbek-specific), apostrophes, hyphens, spaces
_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳӨө\s'.-]{2,50}$")


def validate_name(name: str) -> bool:
    """Name must be 2-50 chars, only letters / spaces / basic punctuation.
    Must contain at least 2 letters."""
    if not name:
        return False
    name = name.strip()
    if len(name) < 2 or len(name) > 50:
        return False
    if not _NAME_RE.match(name):
        return False
    # At least 2 letters
    letters = sum(1 for ch in name if ch.isalpha())
    return letters >= 2


def validate_phone(phone: str) -> str | None:
    """Return normalized phone in +998XXXXXXXXX form, or None if invalid.

    Accepts:
      +998901234567  -> +998901234567
      998901234567   -> +998901234567
      901234567      -> +998901234567
      0901234567     -> +998901234567
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 10 and digits.startswith("0"):
        return f"+998{digits[1:]}"
    return None


def validate_address(address: str) -> bool:
    """Address must be >=5 chars and contain at least 3 letters.
    Rejects pure numbers or 1-2 char inputs."""
    if not address:
        return False
    address = address.strip()
    if len(address) < 5:
        return False
    letters = sum(1 for ch in address if ch.isalpha())
    return letters >= 3
