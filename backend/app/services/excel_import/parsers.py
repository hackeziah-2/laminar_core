"""Value normalization helpers for spreadsheet import."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional, Tuple


FLEXIBLE_DATETIME_FORMATS: Tuple[str, ...] = (
    "%d-%b-%y %H%MZ",
    "%d-%b-%Y %H%MZ",
    "%d-%b-%y %H%M",
    "%d-%b-%Y %H%M",
    "%d-%b-%y",
    "%d-%b-%Y",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
)

INVALID_FLEXIBLE_DATETIME_MESSAGE = (
    "Invalid date. Accepted formats include D-Mon-YY HHMMZ, DD-Mon-YYYY HHMMZ, "
    "date-only values such as DD-Mon-YYYY, or ISO 8601 datetime."
)

_EMPTY_DATETIME_TOKENS = frozenset(
    {"", "-", "NA", "N/A", "NULL", "NONE", "NAN"}
)


def is_spreadsheet_empty(value: Any) -> bool:
    """True for None, pandas NaT/NaN, non-finite floats, and blank strings."""
    if value is None:
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (TypeError, ValueError, ImportError):
        pass
    if isinstance(value, float) and (math.isnan(value) or not math.isfinite(value)):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def sanitize_spreadsheet_value(value: Any) -> Any:
    """Convert pandas NaT/NaN and similar sentinels to None for DB-bound payloads."""
    if is_spreadsheet_empty(value):
        return None
    return value


def normalize_import_numeric_string(value: str) -> str:
    """Strip whitespace/commas from spreadsheet numeric text (e.g. ``17588. 11``)."""
    return re.sub(r"\s+", "", value.strip().replace(",", ""))


def coerce_import_float(value: Any) -> Optional[float]:
    """Parse optional numeric spreadsheet cells; NaN/NaT/blank → None."""
    if is_spreadsheet_empty(value):
        return None
    if isinstance(value, str):
        s = normalize_import_numeric_string(value)
        if not s or s.upper() in ("-", "NA", "N/A"):
            return None
        try:
            x = float(s)
        except ValueError:
            return None
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        x = float(value)
    else:
        return None
    return x if math.isfinite(x) else None


def make_hashable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return tuple(make_hashable(x) for x in obj)
    if isinstance(obj, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in obj.items()))
    try:
        hash(obj)
        return obj
    except TypeError:
        return str(obj)


def _excel_serial_to_date(value: float | int) -> date | None:
    if isinstance(value, float) and (math.isnan(value) or not math.isfinite(value)):
        return None
    if 1 <= float(value) < 100000:
        return (datetime(1899, 12, 30) + timedelta(days=int(float(value)))).date()
    return None


def parse_import_date(v: Any) -> Any:
    """Parse spreadsheet date values (Excel serial, datetime, common string formats)."""
    if is_spreadsheet_empty(v):
        return None
    if isinstance(v, float):
        parsed = _excel_serial_to_date(v)
        if parsed is not None:
            return parsed
        if math.isnan(v) or not math.isfinite(v):
            return None
    if isinstance(v, int) and not isinstance(v, bool):
        parsed = _excel_serial_to_date(v)
        if parsed is not None:
            return parsed
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if hasattr(v, "date") and callable(getattr(v, "date", None)):
        try:
            return v.date()
        except (ValueError, AttributeError, OSError):
            pass
    if isinstance(v, str):
        s = v.strip()
        if not s or s in ("-", "NA", "N/A"):
            return None
        if re.fullmatch(r"\d+(?:\.0+)?", s):
            try:
                fv = float(s)
                parsed = _excel_serial_to_date(fv)
                if parsed is not None:
                    return parsed
            except ValueError:
                pass
        for fmt in (
            "%d/%m/%Y",
            "%d/%m/%y",
            "%d-%b-%y",
            "%d-%b-%Y",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return v


def parse_import_origin_date(v: Any) -> Any:
    return parse_import_date(v)


def _normalize_flexible_datetime_string(value: str) -> str:
    """Trim and normalize month abbreviations (e.g. Sept → Sep)."""
    s = value.strip()
    # Normalize Sept → Sep so %b can parse aviation-style month abbreviations.
    return re.sub(r"(?i)\bSept\b", "Sep", s)


def _string_indicates_zulu(value: str) -> bool:
    upper = value.strip().upper()
    return (
        upper.endswith("Z")
        or " ZULU" in upper
        or upper.endswith(" UTC")
        or upper.endswith("+00:00")
        or upper.endswith("+0000")
    )


def _mark_zulu_as_utc(dt: datetime, *, was_zulu: bool) -> datetime:
    if dt.tzinfo is not None:
        return dt
    if was_zulu:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_flexible_datetime(value: Any) -> Optional[datetime]:
    """Parse flexible ATL Date Time Reported / Date Time Released values.

    Accepts D[D]-Mon-YY[YY] [HHMMZ], ISO 8601 datetime, and native Excel
    date/datetime. Empty / blank / NULL / NaN → ``None``. Invalid values raise
    ``ValueError``.

    Zulu (``Z`` / UTC) values are returned as timezone-aware UTC datetimes.
    Date-only values use ``00:00:00`` (naive). Other naive wall-clock values
    are returned naive for the caller to store per application timezone policy.
    """
    if is_spreadsheet_empty(value):
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.min)

    if hasattr(value, "to_pydatetime"):
        try:
            converted = value.to_pydatetime()
            if isinstance(converted, datetime):
                return converted
        except Exception:
            pass

    if not isinstance(value, str):
        raise ValueError(INVALID_FLEXIBLE_DATETIME_MESSAGE)

    raw = value.strip()
    if not raw or raw.upper() in _EMPTY_DATETIME_TOKENS:
        return None

    s = _normalize_flexible_datetime_string(raw)
    was_zulu = _string_indicates_zulu(s)

    # Collapse optional space before trailing Zulu marker: "0738 Z" → "0738Z"
    s_compact = re.sub(r"\s+Z$", "Z", s, flags=re.IGNORECASE)
    s_compact = re.sub(r"\s+ZULU$", "Z", s_compact, flags=re.IGNORECASE)
    s_compact = re.sub(r"\s+UTC$", "Z", s_compact, flags=re.IGNORECASE)

    for fmt in FLEXIBLE_DATETIME_FORMATS:
        for candidate in (s_compact, s):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return _mark_zulu_as_utc(parsed, was_zulu=was_zulu)
            except ValueError:
                continue

    # fromisoformat handles many ISO variants (including offsets).
    iso_candidate = s_compact
    if iso_candidate.upper().endswith("Z") and "T" in iso_candidate:
        iso_candidate = iso_candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        return _mark_zulu_as_utc(
            parsed, was_zulu=was_zulu or parsed.tzinfo is not None
        )
    except ValueError:
        pass

    raise ValueError(INVALID_FLEXIBLE_DATETIME_MESSAGE)


def normalize_import_nature_of_flight(v: Any) -> Any:
    if v is None or not isinstance(v, str):
        return v
    raw = v.strip()
    if not raw:
        return v

    cleaned = re.sub(r"[\./-]+", " ", raw.upper())
    cleaned = " ".join(cleaned.split())

    if cleaned in {"MISSING", "NO ENTRY", "BLANK"}:
        return None

    if re.search(r"\bEGR\b", cleaned):
        return "EGR"

    alias_map = {
        "TR W PIREM": "TR_WITH_PIREM",
        "TR/ PIREM": "TR_WITH_PIREM",
        "TR/PIREM": "TR_WITH_PIREM",
        "TR W/PIRM": "TR_WITH_PIREM",
        "ATL REPLENISHMENT": "ATL_REPL",
        "ATL REPLENISHNMENT": "ATL_REPL",
        "ATL REPLENISHMENTL": "ATL_REPL",
        "ATL REPLENISHMENTLENISHNMENT": "ATL_REPL",
        "ATL REPELENISHMENT": "ATL_REPL",
        "ATL REPLENSHMENT": "ATL_REPL",
        "ATL REP": "ATL_REPL",
        "ATP REP": "ATL_REPL",
        "MAINT ENTRY": "ME",
        "MAINTENANCE ENTRY": "ME",
        "MAINT ENTRY.": "ME",
        "MAINT. ENTRY": "ME",
        "MAINT ENRTY.": "ME",
        "M.E":"ME",
        "ME": "ME",
        "PST": "PSF",
        "PRE": "PRF",
        "CANCELLED FLT": "CANCELLED_FLT",
    }
    if cleaned in alias_map:
        return alias_map[cleaned]

    canonical = cleaned.replace(" ", "_")
    if canonical in {
        "TR",
        "PSF",
        "PRF",
        "EGR",
        "ME",
        "TR_WITH_PIREM",
        "VOID",
        "ATL_REPL",
        "CANCELLED_FLT",
    }:
        return canonical
    return v
