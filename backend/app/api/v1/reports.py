"""Read-only fleet reports."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.fleet_daily_update import _status_from_str
from app.schemas.aircraft_fleet_dashboard_schema import AircraftFleetDashboardResponse
from app.services.aircraft_fleet_dashboard_service import get_aircraft_fleet_dashboard

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports"],
)

_DASHBOARD_PAGE_SIZE = 20
_STATUS_DETAIL = "status must be one of: Operational, Ongoing Maintenance, AOG"


@router.get(
    "/aircraft-fleet-dashboard",
    response_model=AircraftFleetDashboardResponse,
    summary="Aircraft fleet magneto dashboard",
    description=(
        "One item per registered aircraft (non-deleted Aircraft rows, ordered by "
        "display_order like Daily Fleet Update). "
        "Each item attaches that aircraft's Daily Fleet Update and magneto TCC "
        "components (description containing MAGNETO, such as RH MAGNETO, "
        "LH MAGNETO, or MAGNETO). "
        "Aircraft with no Daily Fleet Update return status and eod_tach as null. "
        "Aircraft with no magneto TCC records return components as an empty array. "
        "due_for_replacement_tach is TCC last_done_tach. "
        "remaining_hours is TCC remaining_tach and is read-only. "
        "Search matches aircraft registration. Status filters the Daily Fleet "
        "Update status on this same aircraft set. "
        "Pagination is by aircraft: page (default 1), page_size (default 20, max 500)."
    ),
)
async def api_aircraft_fleet_dashboard(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        _DASHBOARD_PAGE_SIZE,
        ge=1,
        le=500,
        description="Aircraft per page. Default 20.",
    ),
    search: Optional[str] = Query(
        None,
        description="Search by aircraft registration (partial match)",
    ),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by Daily Fleet Update status: Operational, Ongoing Maintenance, AOG",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Return a page of registered aircraft with fleet and magneto data attached."""
    status_value = None
    if status_filter and status_filter.strip():
        status_value = _status_from_str(status_filter)
        if status_value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=_STATUS_DETAIL,
            )
    return await get_aircraft_fleet_dashboard(
        session,
        page=page,
        page_size=page_size,
        search=search,
        status=status_value,
    )
