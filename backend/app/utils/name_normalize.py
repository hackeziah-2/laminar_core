"""Shared helpers for normalizing person name fields."""
from typing import Optional


def normalize_name(value: Optional[str]) -> Optional[str]:
    """Trim and uppercase a name value.

    - None stays None (not converted to \"NULL\"/\"NONE\").
    - Empty string stays empty after strip (\"\" / whitespace-only -> \"\").
    - Non-empty strings are returned as value.strip().upper().
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return value.strip().upper()


def format_full_name_upper(
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> str:
    """Build an uppercase full name as FIRST [MIDDLE] LAST, skipping null/empty parts."""
    parts = []
    for part in (first_name, middle_name, last_name):
        normalized = normalize_name(part)
        if normalized:
            parts.append(normalized)
    return " ".join(parts)
