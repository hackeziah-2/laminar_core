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
from app.repository.ldnd_monitoring import get_ldnd_latest_by_aircraft
from app.repository.aircraft_technical_log import get_latest_aircraft_technical_log
from app.repository.tcc_maintenance import get_latest_tcc_by_aircraft_and_description
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation

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


def _remaining_or_zero(value: Optional[float]) -> float:
    """Return value if not None, else 0."""
    return value if value is not None else 0.0


def _round1(value: Optional[float]) -> Optional[float]:
    """Return value rounded to one decimal place, or None if value is None."""
    return round(value, 1) if value is not None else None


async def _enrich_item_with_ldnd(session, orm_item):
    """Build list item with next_insp_due, tach_time_due from LDND latest, tach_time_eod from latest ATL,
    and remaining_time_before_next_isp / remaining_time_before_engine / remaining_time_before_propeller."""
    base = _fleet_daily_update_item_with_aircraft(orm_item)
    aircraft_id = orm_item.aircraft_fk
    ldnd = await get_ldnd_latest_by_aircraft(session, aircraft_id)
    # next_insp_due: from next_inspection_due + next_inspection_unit (e.g. "100 HRS")
    if ldnd and ldnd.next_inspection_due is not None:
        unit = ldnd.next_inspection_unit or ldnd.unit or "HRS"
        base["next_insp_due"] = f"{ldnd.next_inspection_due} {unit}"
    else:
        base["next_insp_due"] = None
    # tach_time_due: from next_due_tach_hours (latest record), rounded to one decimal
    raw_tach_due = ldnd.next_due_tach_hours if ldnd else None
    base["tach_time_due"] = _round1(raw_tach_due)
    # tach_time_eod: from latest ATL by sequence_no → tachometer_end, rounded to one decimal
    latest_atl = await get_latest_aircraft_technical_log(session, aircraft_fk=aircraft_id)
    tach_time_eod = latest_atl.tachometer_end if latest_atl else None
    base["tach_time_eod"] = _round1(tach_time_eod)

    # remaining_time_before_next_isp: tach_time_due - tach_time_eod (from raw values), rounded to one decimal
    remaining_isp = (raw_tach_due - tach_time_eod) if (raw_tach_due is not None and tach_time_eod is not None) else None
    base["remaining_time_before_next_isp"] = round(_remaining_or_zero(remaining_isp), 1)

    # remaining_time_before_engine: (TCC Engine last_done_tach + component_limit_hours) - latest ATL tachometer_end, rounded to one decimal
    tcc_engine = await get_latest_tcc_by_aircraft_and_description(session, aircraft_id, "Engine")
    if (
        tcc_engine is not None
        and tcc_engine.last_done_tach is not None
        and tcc_engine.component_limit_hours is not None
        and tach_time_eod is not None
    ):
        remaining_engine = (tcc_engine.last_done_tach + tcc_engine.component_limit_hours) - tach_time_eod
        base["remaining_time_before_engine"] = round(_remaining_or_zero(remaining_engine), 1)
    else:
        base["remaining_time_before_engine"] = 0.0

    # remaining_time_before_propeller: (TCC Propeller last_done_tach + component_limit_hours) - latest ATL tachometer_end, rounded to one decimal
    tcc_propeller = await get_latest_tcc_by_aircraft_and_description(session, aircraft_id, "Propeller")
    if (
        tcc_propeller is not None
        and tcc_propeller.last_done_tach is not None
        and tcc_propeller.component_limit_hours is not None
        and tach_time_eod is not None
    ):
        remaining_propeller = (tcc_propeller.last_done_tach + tcc_propeller.component_limit_hours) - tach_time_eod
        base["remaining_time_before_propeller"] = round(_remaining_or_zero(remaining_propeller), 1)
    else:
        base["remaining_time_before_propeller"] = 0.0

    return base


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
    """Get paginated list of Fleet Daily Update entries. Search by aircraft registration; filter by status.
    Each item includes next_insp_due and tach_time_due from api/v1/aircraft/{id}/ldnd-monitoring/latest,
    and tach_time_eod from api/v1/aircraft-technical-log/latest?aircraft_fk={id} (tachometer_end)."""
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
    enriched = []
    for i in items:
        enriched.append(await _enrich_item_with_ldnd(session, i))
    return {
        "items": enriched,
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    obj = await create_fleet_daily_update(
        session, payload, audit_account_id=current_account.id
    )
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update any field; send only status and/or remarks to update just those."""
    obj = await update_fleet_daily_update(
        session, update_id, payload, audit_account_id=current_account.id
    )
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Partial update: only provided fields are updated (e.g. status, remarks)."""
    obj = await update_fleet_daily_update(
        session, update_id, payload, audit_account_id=current_account.id
    )
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update status, remarks, etc. for the fleet daily update of this aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    record = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not record:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found for this aircraft")
    obj = await update_fleet_daily_update(
        session, record.id, payload, audit_account_id=current_account.id
    )
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Partial update: only send status and/or remarks to update those."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    record = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not record:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found for this aircraft")
    obj = await update_fleet_daily_update(
        session, record.id, payload, audit_account_id=current_account.id
    )
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
    enriched = []
    for i in items:
        enriched.append(await _enrich_item_with_ldnd(session, i))
    return {
        "items": enriched,
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    data = payload.dict(exclude_unset=True)
    data["aircraft_fk"] = aircraft_id
    create_payload = fleet_daily_update_schema.FleetDailyUpdateCreate(**data)
    obj = await create_fleet_daily_update(
        session, create_payload, audit_account_id=current_account.id
    )
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
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update by explicit update_id; path must match the record’s aircraft. Prefer PUT /{aircraft_id}/fleet-daily-update when you only have aircraft_id."""
    existing = await get_fleet_daily_update_by_aircraft(session, aircraft_id)
    if not existing or existing.id != update_id:
        raise HTTPException(status_code=404, detail="Fleet Daily Update not found")
    obj = await update_fleet_daily_update(
        session, update_id, payload, audit_account_id=current_account.id
    )
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
