"""Encode/decode ATL import summary on job message (no extra DB column required)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

_SUMMARY_MARKER = "\n---ATL_IMPORT_SUMMARY---\n"


def encode_message_with_summary(message: str, summary: Dict[str, Any]) -> str:
    base = (message or "").split(_SUMMARY_MARKER, 1)[0].rstrip()
    return f"{base}{_SUMMARY_MARKER}{json.dumps(summary)}"


def decode_summary_from_message(message: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message or _SUMMARY_MARKER not in message:
        return None
    _, raw = message.split(_SUMMARY_MARKER, 1)
    try:
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def display_message(message: Optional[str]) -> Optional[str]:
    """User-facing message without the embedded summary JSON block."""
    if not message:
        return message
    if _SUMMARY_MARKER in message:
        return message.split(_SUMMARY_MARKER, 1)[0].rstrip() or None
    return message
