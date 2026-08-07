from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.fleet_daily_update import get_dashboard_counts
from app.schemas.aircraft_fuel_report_schema import (
    AircraftFuelReportQuery,
    AircraftFuelReportResponse,
)
from app.services.aircraft_fuel_report_service import (
    get_aircraft_fuel_report,
    parse_aircraft_filter,
    parse_aircraft_id_filter,
)

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
    summary="Monthly aircraft fuel consumption report",
    description=(
        "Monthly fleet fuel/hours rollup from approved/completed ATL Logbook rows. "
        "Month bucket = ORIGIN DATE (fallback: reporting date). "
        "Hours = RUN TIME (airframe_run_time, with auto/tach fallbacks; null→0). "
        "Fuel = (PRIOR DEP L+R) − (AFTER ON-BLKS L+R); null fuel/oil/landings→0. "
        "Fuel burn / hour = SUM(fuel) / SUM(hours) (null when hours are zero). "
        "Oil = OIL PRIOR DEP − OIL AFTER ON-BLKS. Landings = NO OF LND. "
        "Optional filters: start_month/end_month (YYYY-MM), "
        "aircraft (comma-separated tails), aircraft_id (comma-separated PKs)."
    ),
)
async def api_aircraft_fuel_report(
    start_month: Optional[str] = Query(
        None,
        description="Inclusive start month YYYY-MM (default: earliest available)",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    end_month: Optional[str] = Query(
        None,
        description="Inclusive end month YYYY-MM (default: latest available)",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    aircraft: Optional[str] = Query(
        None,
        description="Optional comma-separated aircraft tail numbers (e.g. RP-C12,RP-C14)",
    ),
    aircraft_id: Optional[str] = Query(
        None,
        description="Optional comma-separated aircraft ids (e.g. 1,2)",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Return monthly summary, per-aircraft breakdown, and data-quality flags."""
    try:
        aircraft_ids = parse_aircraft_id_filter(aircraft_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid aircraft_id: {exc}",
        ) from exc

    try:
        query = AircraftFuelReportQuery(
            start_month=start_month,
            end_month=end_month,
            aircraft=parse_aircraft_filter(aircraft),
            aircraft_ids=aircraft_ids,
        )
    except ValidationError as exc:
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
