from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import fleet_daily_update_schema
from app.repository.fleet_daily_update import (
    create_fleet_daily_update,
    get_fleet_daily_update,
    get_fleet_daily_update_by_aircraft,
    list_fleet_daily_updates,
    update_fleet_daily_update,
    soft_delete_fleet_daily_update,
    soft_delete_fleet_daily_update_by_aircraft,
)
from app.repository.aircraft import get_aircraft
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/fleet-daily-update",
    tags=["fleet-daily-update"],
)

router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["fleet-daily-update"],
)


def _fleet_daily_update_item_with_aircraft(orm):
    """Build list item dict with aircraft: { id, registration }."""
    read = fleet_daily_update_schema.FleetDailyUpdateRead.from_orm(orm)
    d = read.dict()
    d["aircraft"] = (
        {"id": orm.aircraft.id, "registration": orm.aircraft.registration}
        if orm.aircraft is not None
        else None
    )
    return d


@router.get("/paged")
async def api_list_fleet_daily_updates_paged(
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    search: Optional[str] = Query(
        None,
        description="Search by aircraft registration (partial match)",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status: Running, Ongoing Maintenance, AOG",
    ),
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    sort: Optional[str] = Query(
        "",
        description="Sort fields (comma-separated). Prefix '-' for descending. E.g. -created_at,status",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of Fleet Daily Update entries. Search by aircraft registration; filter by status."""
    offset = (page - 1) * limit
    items, total = await list_fleet_daily_updates(
        session=session,
        limit=limit,
        offset=offset,
        search=search.strip() if search and search.strip() else None,
        aircraft_fk=aircraft_fk,
        status=status,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [_fleet_daily_update_item_with_aircraft(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/{update_id}",
    summary="Get Fleet Daily Update by ID",
    description="Returns fleet daily update with aircraft: { id, registration }.",
)
async def api_get_fleet_daily_update(
    update_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_fleet_daily_update(session, update_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Fleet Daily Update entry",
    description="One record per aircraft (one-to-one). aircraft_fk required. Returns body with aircraft: { id, registration }.",
)
async def api_create_fleet_daily_update(
    payload: fleet_daily_update_schema.FleetDailyUpdateCreate,
    session: AsyncSession = Depends(get_session),
):
    obj = await create_fleet_daily_update(session, payload)
    return _fleet_daily_update_item_with_aircraft(obj)


@router.put(
    "/{update_id}",
    summary="Update Fleet Daily Update by ID (full or partial)",
    description="Returns body with aircraft: { id, registration }.",
)
async def api_update_fleet_daily_update(
    update_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update any field; send only status and/or remarks to update just those."""
    obj = await update_fleet_daily_update(session, update_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router.patch(
    "/{update_id}",
    summary="Partial update (e.g. status, remarks only)",
    description="Returns body with aircraft: { id, registration }.",
)
async def api_patch_fleet_daily_update(
    update_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Partial update: only provided fields are updated (e.g. status, remarks)."""
    obj = await update_fleet_daily_update(session, update_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router.delete(
    "/{update_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete Fleet Daily Update entry",
)
async def api_delete_fleet_daily_update(
    update_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await soft_delete_fleet_daily_update(session, update_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return None


# ========== Aircraft-scoped: /api/v1/aircraft/{aircraft_id}/fleet-daily-update/... ==========


@router_aircraft_scoped.get(
    "/{aircraft_id}/fleet-daily-update",
    summary="Get Fleet Daily Update for aircraft (one-to-one)",
    description="Returns the single Fleet Daily Update for this aircraft with aircraft: { id, registration }, or 404 if none.",
)
async def api_get_fleet_daily_update_by_aircraft(
    aircraft_id: int,
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    obj = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found for this aircraft")
    return _fleet_daily_update_item_with_aircraft(obj)


@router_aircraft_scoped.put(
    "/{aircraft_id}/fleet-daily-update",
    summary="Update Fleet Daily Update for aircraft (by aircraft ID)",
    description="Update the single Fleet Daily Update for this aircraft. Returns body with aircraft: { id, registration }.",
)
async def api_update_fleet_daily_update_by_aircraft_only(
    aircraft_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update status, remarks, etc. for the fleet daily update of this aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    record = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not record:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found for this aircraft")
    obj = await update_fleet_daily_update(session, record.id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router_aircraft_scoped.patch(
    "/{aircraft_id}/fleet-daily-update",
    summary="Partial update for aircraft (e.g. status, remarks only)",
    description="Returns body with aircraft: { id, registration }.",
)
async def api_patch_fleet_daily_update_by_aircraft(
    aircraft_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Partial update: only send status and/or remarks to update those."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    record = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not record:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found for this aircraft")
    obj = await update_fleet_daily_update(session, record.id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router_aircraft_scoped.get(
    "/{aircraft_id}/fleet-daily-update/paged",
    summary="List Fleet Daily Update for aircraft (paginated; at most one)",
    description="Paginated list filtered by aircraft_id. For one-to-one use GET .../fleet-daily-update to get the single record.",
)
async def api_list_fleet_daily_updates_by_aircraft_paged(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    search: Optional[str] = Query(
        None,
        description="Search by aircraft registration (partial match)",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status: Running, Ongoing Maintenance, AOG",
    ),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    items, total = await list_fleet_daily_updates(
        session=session,
        limit=limit,
        offset=offset,
        search=search.strip() if search and search.strip() else None,
        aircraft_fk=aircraft_id,
        status=status,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [_fleet_daily_update_item_with_aircraft(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.post(
    "/{aircraft_id}/fleet-daily-update/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Fleet Daily Update for aircraft",
    description="One record per aircraft. Creates for the given aircraft_id. Returns body with aircraft: { id, registration }.",
)
async def api_create_fleet_daily_update_by_aircraft(
    aircraft_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateCreate,
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    data = payload.dict(exclude_unset=True)
    data["aircraft_fk"] = aircraft_id
    create_payload = fleet_daily_update_schema.FleetDailyUpdateCreate(**data)
    obj = await create_fleet_daily_update(session, create_payload)
    return _fleet_daily_update_item_with_aircraft(obj)


@router_aircraft_scoped.put(
    "/{aircraft_id}/fleet-daily-update/{update_id}",
    summary="Update Fleet Daily Update by aircraft and update ID",
    description="Returns body with aircraft: { id, registration }.",
)
async def api_update_fleet_daily_update_by_aircraft(
    aircraft_id: int,
    update_id: int,
    payload: fleet_daily_update_schema.FleetDailyUpdateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update by explicit update_id; path must match the record’s aircraft. Prefer PUT /{aircraft_id}/fleet-daily-update when you only have aircraft_id."""
    existing = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not existing or existing.id != update_id:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    obj = await update_fleet_daily_update(session, update_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return _fleet_daily_update_item_with_aircraft(obj)


@router_aircraft_scoped.delete(
    "/{aircraft_id}/fleet-daily-update/{update_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete Fleet Daily Update for aircraft",
)
async def api_delete_fleet_daily_update_by_aircraft(
    aircraft_id: int,
    update_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await soft_delete_fleet_daily_update_by_aircraft(
        session, update_id, aircraft_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    return None
