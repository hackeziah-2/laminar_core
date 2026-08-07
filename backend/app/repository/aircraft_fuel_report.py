"""Repository for monthly Aircraft Fuel Report (ATL Logbook rollup)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus

_FUEL_REPORT_STATUSES: Sequence[WorkStatus] = (
    WorkStatus.APPROVED,
    WorkStatus.COMPLETED,
)

# Month bucket: ORIGIN DATE, with reporting-date fallbacks when origin is null
_MONTH_DATE = func.coalesce(
    AircraftTechnicalLog.origin_date,
    func.date(AircraftTechnicalLog.date_time_reported),
    func.date(AircraftTechnicalLog.atl_date_time_reported),
).label("month_date")

# RUN TIME with practical fallbacks; null → 0
_RUN_TIME = func.coalesce(
    AircraftTechnicalLog.airframe_run_time,
    AircraftTechnicalLog.auto_airframe_run_time,
    AircraftTechnicalLog.tachometer_total,
    0,
).label("run_time")


def _nz(column, label: str):
    """COALESCE(column, 0) labeled for Row attribute access."""
    return func.coalesce(column, 0).label(label)


_FUEL_REPORT_COLUMNS = (
    AircraftTechnicalLog.id,
    AircraftTechnicalLog.sequence_no,
    AircraftTechnicalLog.aircraft_fk,
    Aircraft.registration,
    _MONTH_DATE,
    AircraftTechnicalLog.origin_date,
    _RUN_TIME,
    _nz(AircraftTechnicalLog.fuel_qty_left_uplift_qty, "fuel_qty_left_uplift_qty"),
    _nz(AircraftTechnicalLog.fuel_qty_right_uplift_qty, "fuel_qty_right_uplift_qty"),
    _nz(
        AircraftTechnicalLog.fuel_qty_left_prior_departure,
        "fuel_qty_left_prior_departure",
    ),
    _nz(
        AircraftTechnicalLog.fuel_qty_right_prior_departure,
        "fuel_qty_right_prior_departure",
    ),
    _nz(
        AircraftTechnicalLog.fuel_qty_left_after_on_blks,
        "fuel_qty_left_after_on_blks",
    ),
    _nz(
        AircraftTechnicalLog.fuel_qty_right_after_on_blks,
        "fuel_qty_right_after_on_blks",
    ),
    _nz(AircraftTechnicalLog.oil_qty_uplift_qty, "oil_qty_uplift_qty"),
    _nz(AircraftTechnicalLog.oil_qty_prior_departure, "oil_qty_prior_departure"),
    _nz(AircraftTechnicalLog.oil_qty_after_on_blks, "oil_qty_after_on_blks"),
    _nz(AircraftTechnicalLog.number_of_landings, "number_of_landings"),
)


async def list_aircraft_id_registration_map(
    session: AsyncSession,
) -> Dict[str, int]:
    """Map UPPER(registration) → aircraft id for active aircraft."""
    stmt = (
        select(Aircraft.id, Aircraft.registration)
        .where(Aircraft.is_deleted.is_(False))
    )
    result = await session.execute(stmt)
    out: Dict[str, int] = {}
    for ac_id, reg in result.all():
        if reg is None:
            continue
        key = str(reg).strip().upper()
        if key:
            out[key] = int(ac_id)
    return out


async def list_known_aircraft_registrations(session: AsyncSession) -> List[str]:
    """Active (non-deleted) aircraft registrations, uppercased."""
    mapping = await list_aircraft_id_registration_map(session)
    return sorted(mapping.keys())


async def resolve_aircraft_filter_ids(
    session: AsyncSession,
    *,
    registrations: Sequence[str],
    aircraft_ids: Sequence[int],
) -> Tuple[List[int], List[str], List[int]]:
    """
    Resolve tail numbers and/or aircraft PKs to a deduped list of aircraft ids.

    Returns (resolved_ids, unknown_registrations, unknown_ids).
    """
    mapping = await list_aircraft_id_registration_map(session)
    known_ids = set(mapping.values())
    resolved: List[int] = []
    seen: set[int] = set()
    unknown_regs: List[str] = []
    unknown_ids: List[int] = []

    for reg in registrations:
        key = reg.strip().upper()
        ac_id = mapping.get(key)
        if ac_id is None:
            unknown_regs.append(key)
            continue
        if ac_id not in seen:
            seen.add(ac_id)
            resolved.append(ac_id)

    for ac_id in aircraft_ids:
        if ac_id not in known_ids:
            unknown_ids.append(ac_id)
            continue
        if ac_id not in seen:
            seen.add(ac_id)
            resolved.append(ac_id)

    return resolved, unknown_regs, unknown_ids


async def fetch_fuel_report_available_month_bounds(
    session: AsyncSession,
    *,
    aircraft_ids: Optional[Sequence[int]] = None,
) -> tuple[Optional[date], Optional[date]]:
    """Earliest / latest month date among approved/completed ATLs (optionally aircraft-scoped)."""
    stmt = (
        select(
            func.min(_MONTH_DATE),
            func.max(_MONTH_DATE),
        )
        .select_from(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(AircraftTechnicalLog.work_status.in_(_FUEL_REPORT_STATUSES))
        .where(_MONTH_DATE.is_not(None))
    )
    if aircraft_ids:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk.in_(list(aircraft_ids)))

    result = await session.execute(stmt)
    row = result.one()
    return row[0], row[1]


async def fetch_fuel_report_atl_rows(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    aircraft_ids: Optional[Sequence[int]] = None,
) -> List[Any]:
    """
    Load approved/completed ATL rows with month date in [start_date, end_date].

    Numeric fuel/oil/hours/landings fields are COALESCE'd to 0 in SQL.
    Filter by ``aircraft_fk`` (parameterized IN) when ``aircraft_ids`` is provided.
    """
    stmt = (
        select(*_FUEL_REPORT_COLUMNS)
        .join(Aircraft, Aircraft.id == AircraftTechnicalLog.aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
        .where(AircraftTechnicalLog.work_status.in_(_FUEL_REPORT_STATUSES))
        .where(_MONTH_DATE.is_not(None))
        .where(
            and_(
                _MONTH_DATE >= start_date,
                _MONTH_DATE <= end_date,
            )
        )
        .order_by(
            Aircraft.registration.asc(),
            _MONTH_DATE.asc(),
            AircraftTechnicalLog.id.asc(),
        )
    )

    if aircraft_ids:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk.in_(list(aircraft_ids)))

    result = await session.execute(stmt)
    return list(result.all())
