"""Aircraft fleet dashboard: one page item per registered aircraft."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import page_count
from app.models.aircraft import Aircraft
from app.models.fleet_daily_update import FleetDailyUpdate
from app.models.tcc_maintenance import TCCMaintenance
from app.schemas.aircraft_fleet_dashboard_schema import (
    AircraftFleetDashboardComponent,
    AircraftFleetDashboardItem,
    AircraftFleetDashboardResponse,
)
from app.services.tcc_computation import as_finite_float

_MAGNETO_DESCRIPTION = "%magneto%"


def format_tach_hours(value: Optional[float]) -> Optional[str]:
    """One decimal place, matching fleet tach display (e.g. 500.0, 9.8)."""
    number = as_finite_float(value)
    if number is None:
        return None
    return f"{round(number, 1):.1f}"


def _status_text(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    text = str(value).strip()
    return text or None


def _registered_aircraft_stmt(
    *,
    search: Optional[str],
    status: Optional[str],
):
    """Active aircraft in Fleet Profile / Daily Fleet Update order, with fleet data attached.

    Status filter keeps only aircraft whose Daily Fleet Update matches. Aircraft
    with no update stay in the list when status is not filtered.
    """
    fleet_join = and_(
        FleetDailyUpdate.aircraft_fk == Aircraft.id,
        FleetDailyUpdate.is_deleted == False,
    )
    stmt = select(Aircraft, FleetDailyUpdate).where(Aircraft.is_deleted == False)
    if status:
        stmt = stmt.join(FleetDailyUpdate, fleet_join).where(FleetDailyUpdate.status == status)
    else:
        stmt = stmt.outerjoin(FleetDailyUpdate, fleet_join)
    if search:
        stmt = stmt.where(Aircraft.registration.ilike(f"%{search}%"))
    return stmt


def _component(tcc: TCCMaintenance) -> AircraftFleetDashboardComponent:
    return AircraftFleetDashboardComponent(
        magneto=tcc.description,
        due_for_replacement_tach=format_tach_hours(tcc.last_done_tach),
        remaining_hours=format_tach_hours(tcc.remaining_tach),
        part_number=tcc.part_number,
        serial_number=tcc.serial_number,
    )


async def _magneto_components_by_aircraft(
    session: AsyncSession,
    aircraft_ids: list[int],
) -> dict[int, list[AircraftFleetDashboardComponent]]:
    grouped: dict[int, list[AircraftFleetDashboardComponent]] = defaultdict(list)
    if not aircraft_ids:
        return grouped
    result = await session.execute(
        select(TCCMaintenance)
        .where(TCCMaintenance.aircraft_fk.in_(aircraft_ids))
        .where(TCCMaintenance.is_deleted == False)
        .where(TCCMaintenance.description.ilike(_MAGNETO_DESCRIPTION))
        .order_by(
            TCCMaintenance.display_order.asc(),
            TCCMaintenance.id.asc(),
        )
    )
    for tcc in result.scalars().all():
        grouped[tcc.aircraft_fk].append(_component(tcc))
    return grouped


async def get_aircraft_fleet_dashboard(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: Optional[str] = None,
    status: Optional[str] = None,
) -> AircraftFleetDashboardResponse:
    """Paginate registered aircraft, then attach Daily Fleet Update and magneto TCC rows."""
    search_text = search.strip() if search and search.strip() else None
    filters = _registered_aircraft_stmt(search=search_text, status=status)
    total = await session.scalar(
        select(func.count()).select_from(filters.order_by(None).subquery())
    )
    total = int(total or 0)
    offset = (page - 1) * page_size
    result = await session.execute(
        filters.order_by(Aircraft.display_order.asc(), Aircraft.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()
    components_by_aircraft = await _magneto_components_by_aircraft(
        session,
        [aircraft.id for aircraft, _fleet in rows],
    )
    items = [
        AircraftFleetDashboardItem(
            aircraft_ident=aircraft.registration,
            status=_status_text(fleet.status) if fleet is not None else None,
            eod_tach=format_tach_hours(fleet.tach_time_eod) if fleet is not None else None,
            components=components_by_aircraft.get(aircraft.id, []),
        )
        for aircraft, fleet in rows
    ]
    return AircraftFleetDashboardResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )
