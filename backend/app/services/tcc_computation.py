"""TCC Maintenance derived fields (aligned with TCCDetail.tsx computeTCCRow)."""
from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.aircraft_technical_log import get_latest_aircraft_technical_log

_MS_PER_DAY = 24 * 60 * 60 * 1000

COMPUTED_TCC_COLUMN_KEYS = (
    "next_due_tach",
    "next_due_aftt",
    "next_due_date",
    "remaining_years",
    "remaining_days",
    "remaining_tach",
    "remaining_aftt",
)

# Create/update may override these with explicit values (including negative overdue).
CLIENT_REMAINING_OVERRIDE_KEYS = (
    "remaining_years",
    "remaining_days",
    "remaining_tach",
)


def coerce_stored_remaining_override(key: str, value: Any) -> Optional[float]:
    """Persist client remaining_*; None clears. remaining_years is rounded to 2 decimal places."""
    if value is None:
        return None
    fin = as_finite_float(value)
    if fin is None:
        return None
    if key == "remaining_years":
        return round(fin, 2)
    return fin


def as_finite_float(value: Any) -> Optional[float]:
    """Return float if value is a finite number, else None."""
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def days_between(a: date, b: date) -> int:
    """Truncated day count between calendar dates a and b (same as JS int((b-a)/msPerDay))."""
    ta = datetime(a.year, a.month, a.day, tzinfo=timezone.utc).timestamp() * 1000
    tb = datetime(b.year, b.month, b.day, tzinfo=timezone.utc).timestamp() * 1000
    return int((tb - ta) / _MS_PER_DAY)


def add_calendar_years(d: date, years: int) -> date:
    if years == 0:
        return d
    y = d.year + years
    try:
        return date(y, d.month, d.day)
    except ValueError:
        last_day = calendar.monthrange(y, d.month)[1]
        return date(y, d.month, min(d.day, last_day))


def compute_next_due_date(
    last_done_date: Optional[date],
    limit_years: Optional[float],
) -> Optional[date]:
    if last_done_date is None:
        return None
    ly = as_finite_float(limit_years)
    if ly is None:
        return None
    whole = int(math.floor(ly))
    fractional = ly - whole
    d = add_calendar_years(last_done_date, whole)
    if fractional > 0:
        d = d + timedelta(days=int(math.ceil(fractional * 365.25)))
    return d


def compute_tcc_derived_field_values(
    *,
    last_done_date: Optional[date],
    last_done_tach: Optional[float],
    last_done_aftt: Optional[float],
    component_limit_hours: Optional[float],
    component_limit_years: Optional[float],
    latest_tachometer_end: Optional[float],
    latest_atl_airframe_aftt: Optional[float],
    as_of_date: date,
) -> Dict[str, Any]:
    limit_hours = as_finite_float(component_limit_hours)
    limit_years = as_finite_float(component_limit_years)
    ldt = as_finite_float(last_done_tach)
    lda = as_finite_float(last_done_aftt)

    has_limit_hours = limit_hours is not None
    has_last_done_tach = ldt is not None
    has_last_done_aftt = lda is not None

    next_due_tach = (ldt + limit_hours) if (has_limit_hours and has_last_done_tach) else None
    next_due_aftt = (lda + limit_hours) if (has_limit_hours and has_last_done_aftt) else None
    next_due_date = compute_next_due_date(last_done_date, limit_years)

    remaining_years: Optional[float] = None
    remaining_days: Optional[float] = None
    if next_due_date is not None:
        db = days_between(as_of_date, next_due_date)
        remaining_days = float(db)
        remaining_years = round(float(db) / 365.0, 2)

    # Latest meter readings: highest sequence_no ATL (see fetch_latest_atl_tach_aftt).
    remaining_tach: Optional[float] = None
    ndt = as_finite_float(next_due_tach)
    ct = as_finite_float(latest_tachometer_end)
    if ndt is not None and ct is not None:
        remaining_tach = ndt - ct

    remaining_aftt: Optional[float] = None
    nda = as_finite_float(next_due_aftt)
    ca = as_finite_float(latest_atl_airframe_aftt)
    if nda is not None and ca is not None:
        remaining_aftt = nda - ca

    return {
        "next_due_tach": next_due_tach,
        "next_due_aftt": next_due_aftt,
        "next_due_date": next_due_date,
        "remaining_years": remaining_years,
        "remaining_days": remaining_days,
        "remaining_tach": remaining_tach,
        "remaining_aftt": remaining_aftt,
    }


async def fetch_latest_atl_tach_aftt(
    session: AsyncSession,
    aircraft_fk: int,
) -> Tuple[Optional[float], Optional[float]]:
    """Tachometer_end and airframe_aftt from the latest ATL row for this aircraft (highest sequence_no)."""
    latest = await get_latest_aircraft_technical_log(session, aircraft_fk)
    latest_tach = None
    latest_aftt = None
    if latest is not None:
        latest_tach = as_finite_float(getattr(latest, "tachometer_end", None))
        latest_aftt = as_finite_float(getattr(latest, "airframe_aftt", None))
    return latest_tach, latest_aftt


async def build_computed_tcc_field_values(
    session: AsyncSession,
    *,
    aircraft_fk: int,
    last_done_date: Optional[date],
    last_done_tach: Any,
    last_done_aftt: Any,
    component_limit_hours: Any,
    component_limit_years: Any,
    as_of_date: Optional[date] = None,
    prefetched_latest_atl_tach_aftt: Optional[Tuple[Optional[float], Optional[float]]] = None,
) -> Dict[str, Any]:
    """Compute all server-derived TCC columns for create/update."""
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).date()
    if prefetched_latest_atl_tach_aftt is not None:
        latest_tach, latest_aftt = prefetched_latest_atl_tach_aftt
    else:
        latest_tach, latest_aftt = await fetch_latest_atl_tach_aftt(session, aircraft_fk)
    return compute_tcc_derived_field_values(
        last_done_date=last_done_date,
        last_done_tach=as_finite_float(last_done_tach),
        last_done_aftt=as_finite_float(last_done_aftt),
        component_limit_hours=as_finite_float(component_limit_hours),
        component_limit_years=as_finite_float(component_limit_years),
        latest_tachometer_end=latest_tach,
        latest_atl_airframe_aftt=latest_aftt,
        as_of_date=as_of_date,
    )
