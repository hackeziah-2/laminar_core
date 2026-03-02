from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.fleet_daily_update import get_dashboard_counts
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
)


@router.get(
    "/",
    summary="Dashboard counts by Fleet Daily Update status",
    description="Returns total aircraft and counts by status (Running, Ongoing Maintenance, AOG) from Aircraft Fleet Daily Update.",
)
async def api_dashboard(
    session: AsyncSession = Depends(get_session),
):
    """Get dashboard aggregates: total_aircraft, total_aircraft_running, total_aircraft_ongoing_maintenance, total_aircraft_aog."""
    return await get_dashboard_counts(session)
