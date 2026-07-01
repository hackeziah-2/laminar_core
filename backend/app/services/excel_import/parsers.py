"""Value normalization helpers for spreadsheet import."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional


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


def coerce_import_float(value: Any) -> Optional[float]:
    """Parse optional numeric spreadsheet cells; NaN/NaT/blank → None."""
    if is_spreadsheet_empty(value):
        return None
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if not s or s in ("-", "NA", "N/A"):
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
