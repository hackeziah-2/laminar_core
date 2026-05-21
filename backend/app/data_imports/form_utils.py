"""Parse multipart form values for import context resolvers."""
from __future__ import annotations

from typing import Any, Mapping, Optional, Union


def form_value(form: Mapping[str, Any], key: str) -> Optional[str]:
    raw = form.get(key)
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8", errors="replace")
    return str(raw).strip() or None


def parse_form_optional_int(value: Union[str, int, None]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None
