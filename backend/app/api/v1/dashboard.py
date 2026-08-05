from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.fleet_daily_update import get_dashboard_counts
from app.schemas.aircraft_fuel_report_schema import (
    AircraftFuelReportQuery,
    AircraftFuelReportResponse,
    FuelReportPeriod,
)
from app.services.aircraft_fuel_report_service import get_aircraft_fuel_report

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
)


@router.get(
    "/",
    summary="Dashboard counts by Fleet Daily Update status",
    description="Returns total aircraft and counts by status (Operational, Ongoing Maintenance, AOG) from Aircraft Fleet Daily Update.",
)
async def api_dashboard(
    session: AsyncSession = Depends(get_session),
):
    """Get dashboard aggregates: total_aircraft, total_aircraft_running, total_aircraft_ongoing_maintenance, total_aircraft_aog."""
    return await get_dashboard_counts(session)


@router.get(
    "/aircraft-fuel-report",
    response_model=AircraftFuelReportResponse,
    summary="Aircraft fuel consumption dashboard",
    description=(
        "Aggregates approved/completed Aircraft Technical Log (ATL) fuel and flight-hour "
        "data for weekly, monthly, or yearly charting. Fuel used per ATL is "
        "(prior departure − after on-blocks) for left and right tanks. Flight hours use "
        "persisted airframe_flight_time. Fuel burn / hour is SUM(fuel) / SUM(hours)."
    ),
)
async def api_aircraft_fuel_report(
    period: FuelReportPeriod = Query(
        ...,
        description="Aggregation period: weekly | monthly | yearly",
    ),
    year: int = Query(..., ge=1900, le=2100, description="Reporting year"),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Calendar month (required when period=monthly)",
    ),
    week: Optional[int] = Query(
        None,
        ge=1,
        le=53,
        description="ISO week number (required when period=weekly)",
    ),
    aircraft_id: Optional[int] = Query(
        None,
        ge=1,
        description="Optional aircraft primary key filter",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Return fuel consumption series, per-aircraft breakdown, and grand totals."""
    try:
        query = AircraftFuelReportQuery(
            period=period,
            year=year,
            month=month,
            week=week,
            aircraft_id=aircraft_id,
        )
    except ValidationError as exc:
        # Flatten to a concise detail string for API clients.
        messages = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = err.get("msg", "Invalid value")
            messages.append(f"{loc}: {msg}" if loc else msg)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(messages) or "Invalid query parameters",
        ) from exc

    return await get_aircraft_fuel_report(session, query)
