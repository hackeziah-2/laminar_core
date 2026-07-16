"""ATL import mapping for Excel column ``Date Time Reported``.

Uses existing ``origin_date`` / ``origin_time`` on ``aircraft_technical_log``
as the source of truth once set.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Optional, Tuple

from app.database import PH_TZ
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.services.excel_import.parsers import parse_flexible_datetime


def as_naive_ph(dt: datetime) -> datetime:
    """Normalize to naive Asia/Manila wall-clock for DateTime(timezone=False) columns."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(PH_TZ).replace(tzinfo=None)


def combine_date_and_time(
    d: Optional[date],
    t: Optional[time],
) -> Optional[datetime]:
    """Combine origin date/time into a naive Manila datetime."""
    if d is None:
        return None
    return datetime.combine(d, t or time.min)


def try_parse_atl_date_time_reported(
    value: Any,
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Parse Excel Date Time Reported.

    Returns ``(datetime, None)`` on success, ``(None, "empty")`` when blank,
    or ``(None, "invalid")`` when the value cannot be parsed.

    Zulu (``Z``) times are treated as UTC and converted to Asia/Manila;
    other naive values are treated as Manila wall-clock.
    """
    try:
        parsed = parse_flexible_datetime(value)
    except ValueError:
        return None, "invalid"

    if parsed is None:
        return None, "empty"
    return as_naive_ph(parsed), None


def parse_flexible_datetime_for_storage(value: Any) -> Optional[datetime]:
    """Parse flexible datetime and normalize to naive Asia/Manila for storage.

    Empty → ``None``. Invalid → raises ``ValueError`` with the shared message.
    """
    parsed = parse_flexible_datetime(value)
    if parsed is None:
        return None
    return as_naive_ph(parsed)


@dataclass(frozen=True)
class DateTimeReportedResolution:
    """Fields to apply for one imported sequence_no."""

    atl_date_time_reported: Optional[datetime]
    origin_date: Optional[date] = None
    origin_time: Optional[time] = None
    set_origin: bool = False


def resolve_date_time_reported(
    *,
    existing: Optional[AircraftTechnicalLog],
    imported_dt: Optional[datetime],
) -> DateTimeReportedResolution:
    """
    Scenario 1 — existing origin_date empty:
      store imported value in atl_date_time_reported and split into origin_*.
    Scenario 2 — existing origin_date present:
      keep origin_*; set atl_date_time_reported from existing origin date+time.
    """
    existing_origin_date = getattr(existing, "origin_date", None) if existing else None
    existing_origin_time = getattr(existing, "origin_time", None) if existing else None

    if existing_origin_date is not None:
        return DateTimeReportedResolution(
            atl_date_time_reported=combine_date_and_time(
                existing_origin_date,
                existing_origin_time,
            ),
            set_origin=False,
        )

    if imported_dt is None:
        return DateTimeReportedResolution(
            atl_date_time_reported=None,
            set_origin=False,
        )

    naive = as_naive_ph(imported_dt)
    return DateTimeReportedResolution(
        atl_date_time_reported=naive,
        origin_date=naive.date(),
        origin_time=naive.time(),
        set_origin=True,
    )


def apply_date_time_reported_resolution(
    target: AircraftTechnicalLog,
    resolution: DateTimeReportedResolution,
) -> None:
    """Mutate ATL instance from a resolved Date Time Reported mapping."""
    target.atl_date_time_reported = resolution.atl_date_time_reported
    if resolution.set_origin:
        target.origin_date = resolution.origin_date
        target.origin_time = resolution.origin_time
