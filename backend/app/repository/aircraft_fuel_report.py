"""Repository for Aircraft Fuel Consumption Dashboard ATL queries."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, List, Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus

# Approved or completed ATLs only (dashboard fuel reporting).
_FUEL_REPORT_STATUSES: Sequence[WorkStatus] = (
    WorkStatus.APPROVED,
    WorkStatus.COMPLETED,
)

_FUEL_REPORT_COLUMNS = (
    AircraftTechnicalLog.id,
    AircraftTechnicalLog.aircraft_fk,
    Aircraft.registration,
    AircraftTechnicalLog.atl_date_time_reported,
    AircraftTechnicalLog.airframe_flight_time,
    AircraftTechnicalLog.fuel_qty_left_prior_departure,
    AircraftTechnicalLog.fuel_qty_right_prior_departure,
    AircraftTechnicalLog.fuel_qty_left_after_on_blks,
    AircraftTechnicalLog.fuel_qty_right_after_on_blks,
    AircraftTechnicalLog.oil_qty_prior_departure,
    AircraftTechnicalLog.oil_qty_after_on_blks,
    AircraftTechnicalLog.work_status,
)


def _range_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """Inclusive calendar range as naive Manila datetimes for atl_date_time_reported."""
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max.replace(microsecond=999999))
    return start_dt, end_dt


async def fetch_fuel_report_atl_rows(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    aircraft_id: Optional[int] = None,
) -> List[Any]:
    """
    Load approved/completed ATL rows in the reporting window.

    Returns Row objects with columns needed for fuel aggregation.
    Soft-deleted ATLs and aircraft are excluded.
    """
    start_dt, end_dt = _range_bounds(start_date, end_date)

    stmt = (
        select(*_FUEL_REPORT_COLUMNS)
        .join(Aircraft, Aircraft.id == AircraftTechnicalLog.aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
        .where(AircraftTechnicalLog.work_status.in_(_FUEL_REPORT_STATUSES))
        .where(AircraftTechnicalLog.atl_date_time_reported.is_not(None))
        .where(
            and_(
                AircraftTechnicalLog.atl_date_time_reported >= start_dt,
                AircraftTechnicalLog.atl_date_time_reported <= end_dt,
            )
        )
        .order_by(
            Aircraft.registration.asc(),
            AircraftTechnicalLog.atl_date_time_reported.asc(),
            AircraftTechnicalLog.id.asc(),
        )
    )

    if aircraft_id is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_id)

    result = await session.execute(stmt)
    return list(result.all())
