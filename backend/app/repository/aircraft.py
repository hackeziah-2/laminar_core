import os
from typing import List, Optional, Tuple, Union

from sqlalchemy import select, or_, cast, String
from sqlalchemy.sql import func
from fastapi import Query, Depends, UploadFile, File, Form, HTTPException, Request, status as http_status

from sqlalchemy.ext.asyncio import AsyncSession

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

ensure_uploads_dir()

from app.models.aircraft import Aircraft, StatusEnum
from app.models.fleet_daily_update import FleetDailyUpdate, FleetDailyUpdateStatusEnum
from app.models.aircraft_logbook_entries import AircraftLogbookEntry
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_monitoring import LDNDMonitoring
from app.models.ad_monitoring import ADMonitoring, WorkOrderADMonitoring
from app.models.logbooks import (
    EngineLogbook,
    AirframeLogbook,
    AvionicsLogbook,
    PropellerLogbook,
)
from app.models.tcc_maintenance import TCCMaintenance
from app.models.document_on_board import DocumentOnBoard
from app.models.cpcp_monitoring import CPCPMonitoring
from app.schemas.aircraft_schema import (
    AircraftCreate,
    AircraftOut,
    AircraftReorderItem,
    AircraftReorderResponse,
    AircraftUpdate,
)
from app.database import active_query, set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.services.display_order_reorder import validate_reorder_items


async def _next_aircraft_display_order(session: AsyncSession) -> int:
    """
    Return MAX(active display_order) + 1, concurrency-safe via row lock on the
    current last active aircraft (when any exist).
    """
    lock_result = await session.execute(
        select(Aircraft)
        .where(Aircraft.is_deleted == False)
        .order_by(Aircraft.display_order.desc(), Aircraft.id.desc())
        .limit(1)
        .with_for_update()
    )
    top = lock_result.scalar_one_or_none()
    if top is None:
        return 1
    return int(top.display_order or 0) + 1


async def _normalize_aircraft_display_order(session: AsyncSession) -> None:
    """Renumber remaining active aircraft to contiguous 1..N."""
    result = await session.execute(
        select(Aircraft)
        .where(Aircraft.is_deleted == False)
        .order_by(Aircraft.display_order.asc(), Aircraft.id.asc())
    )
    for index, row in enumerate(result.scalars().all(), start=1):
        if row.display_order != index:
            row.display_order = index
            session.add(row)


async def place_restored_aircraft_at_end(
    session: AsyncSession,
    aircraft: Aircraft,
) -> None:
    """After undeleting an aircraft, append it to the end of the active fleet order."""
    next_order = await _next_aircraft_display_order(session)
    aircraft.is_deleted = False
    aircraft.display_order = next_order
    session.add(aircraft)


async def _sync_fleet_daily_update_when_aircraft_maintenance(
    session: AsyncSession,
    aircraft: Aircraft,
    *,
    audit_account_id: Optional[int] = None,
) -> None:
    """If aircraft is in Maintenance, align Fleet Daily Update status to Ongoing Maintenance."""
    st = aircraft.status
    st_val = st.value if hasattr(st, "value") else str(st)
    if st_val != StatusEnum.MAINTENANCE.value:
        return
    fd_res = await session.execute(
        select(FleetDailyUpdate).where(
            FleetDailyUpdate.aircraft_fk == aircraft.id,
            FleetDailyUpdate.is_deleted == False,
        )
    )
    fd = fd_res.scalar_one_or_none()
    if not fd:
        return
    fd_st = fd.status
    fd_st_val = fd_st.value if hasattr(fd_st, "value") else str(fd_st)
    if fd_st_val != FleetDailyUpdateStatusEnum.ONGOING_MAINTENANCE.value:
        fd.status = FleetDailyUpdateStatusEnum.ONGOING_MAINTENANCE.value
        if audit_account_id is not None:
            await set_audit_fields(fd, audit_account_id, is_create=False)
        session.add(fd)


async def _find_active_aircraft_by_field(
    session: AsyncSession,
    field_name: str,
    value: str,
    *,
    exclude_id: Optional[int] = None,
) -> Optional[Aircraft]:
    """Return an active (non-soft-deleted) aircraft matching a unique field."""
    stmt = active_query(Aircraft).where(getattr(Aircraft, field_name) == value)
    if exclude_id is not None:
        stmt = stmt.where(Aircraft.id != exclude_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _persist_upload_file(upload_file: UploadFile) -> str:
    file_path = os.path.join(str(UPLOAD_DIR), upload_file.filename)
    with open(file_path, "wb") as f:
        f.write(await upload_file.read())
    return file_path

def _normalize_status(status: Optional[Union[str, object]]) -> Optional[str]:
    """Return a string status for filtering: 'all', 'active', 'inactive', 'maintenance', or None (treated as all)."""
    if status is None:
        return None
    if hasattr(status, "value"):
        return str(status.value)
    return str(status).strip() or None

async def get_aircraft(session: AsyncSession, id: int) -> Optional[AircraftOut]:
    aircraft = await get_aircraft_raw(session, id)
    if not aircraft:
        return None
    return AircraftOut.from_orm(aircraft)


async def get_aircraft_raw(session: AsyncSession, id: int):
    """Return the Aircraft ORM model or None (for internal use, e.g. file paths)."""
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    return result.scalar_one_or_none()

async def list_aircraft(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    status: Optional[str] = "all",
    sort: Optional[str] = "",
):
    atl_count_subquery = (
        select(func.count(AircraftTechnicalLog.id))
        .where(
            AircraftTechnicalLog.aircraft_fk == Aircraft.id,
            AircraftTechnicalLog.is_deleted == False,
        )
        .correlate(Aircraft)
        .scalar_subquery()
    )

    stmt = (
        select(Aircraft, atl_count_subquery.label("atl_count"))
        .where(Aircraft.is_deleted == False)
    )

    # Search
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                Aircraft.registration.ilike(q),
                Aircraft.base.ilike(q),
                Aircraft.model.ilike(q),
                Aircraft.msn.ilike(q),
            )
        )

    # Status filter (accept string or enum; normalize to string)
    status_val = _normalize_status(status)
    if status_val and status_val.lower() != "all":
        stmt = stmt.where(
            func.lower(cast(Aircraft.status, String)) == status_val.lower()
        )

    # Whitelist sortable fields (IMPORTANT)
    sortable_fields = {
        "registration": Aircraft.registration,
        "base": Aircraft.base,
        "model": Aircraft.model,
        "status": Aircraft.status,
        "display_order": Aircraft.display_order,
        "created_at": Aircraft.created_at,
        "updated_at": Aircraft.updated_at,
    }
    
    # Multi-sort logic (accumulate order_by clauses so multiple sorts work)
    if sort:
        order_clauses = []
        for field in sort.split(","):
            part = field.strip()
            if not part:
                continue
            desc_order = part.startswith("-")
            field_name = part.lstrip("-").strip()
            column = sortable_fields.get(field_name)
            if column is None:
                continue
            order_clauses.append(column.desc() if desc_order else column.asc())
        if order_clauses:
            stmt = stmt.order_by(*order_clauses, Aircraft.id.asc())
        else:
            stmt = stmt.order_by(Aircraft.display_order.asc(), Aircraft.id.asc())
    else:
        stmt = stmt.order_by(Aircraft.display_order.asc(), Aircraft.id.asc())

    # Total count (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(Aircraft)
        .where(Aircraft.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                Aircraft.registration.ilike(q),
                Aircraft.base.ilike(q),
                Aircraft.model.ilike(q),
            )
        )

    if status_val and status_val.lower() != "all":
        count_stmt = count_stmt.where(
            func.lower(cast(Aircraft.status, String)) == status_val.lower()
        )

    total_count = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    rows = result.all()
    items = []
    for aircraft, atl_count in rows:
        setattr(aircraft, "atl_count", int(atl_count or 0))
        items.append(aircraft)

    return items, total_count


async def list_aircraft_minimal(session: AsyncSession) -> List[Aircraft]:
    result = await session.execute(
        select(Aircraft)
        .where(Aircraft.is_deleted == False)
        .order_by(Aircraft.display_order.asc(), Aircraft.id.asc())
    )
    return result.scalars().all()


async def update_aircraft(
    session: AsyncSession,
    aircraft_id: int,
    aircraft_in: AircraftUpdate,
    *,
    audit_account_id: Optional[int] = None,
) -> Optional[Aircraft]:
    obj = await session.get(Aircraft, aircraft_id)
    if not obj:
        return None
    for k, v in aircraft_in.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    await _sync_fleet_daily_update_when_aircraft_maintenance(
        session, obj, audit_account_id=audit_account_id
    )
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)
    return obj

async def create_aircraft_with_file(
    session: AsyncSession,
    data: AircraftCreate,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
):  
    engine_path = None
    if engine_file:
        engine_path = await _persist_upload_file(engine_file)

    propeller_path = None
    if propeller_file:
        propeller_path = await _persist_upload_file(propeller_file)

    aircraft_data = data.dict()

    if engine_path:
        aircraft_data["engine_arc"] = engine_path

    if propeller_path:
        aircraft_data["propeller_arc"] = propeller_path

    if await _find_active_aircraft_by_field(
        session, "registration", aircraft_data["registration"]
    ):
        raise HTTPException(status_code=400, detail="Aircraft with this registration already exists")

    if await _find_active_aircraft_by_field(session, "msn", aircraft_data["msn"]):
        raise HTTPException(status_code=400, detail="Aircraft with this msn already exists")

    aircraft_data["display_order"] = await _next_aircraft_display_order(session)

    aircraft = Aircraft(
        **aircraft_data
    )

    session.add(aircraft)
    await session.flush()  # get aircraft.id before creating fleet_daily_update

    # One-to-one: each aircraft has exactly one FleetDailyUpdate
    fleet_daily_update = FleetDailyUpdate(
        aircraft_fk=aircraft.id,
        status=FleetDailyUpdateStatusEnum.OP.value,
    )
    session.add(fleet_daily_update)

    if audit_account_id is not None:
        await set_audit_fields(aircraft, audit_account_id, is_create=True)
        await set_audit_fields(fleet_daily_update, audit_account_id, is_create=True)

    await session.commit()
    await session.refresh(aircraft)

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=aircraft.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=aircraft,
            current_user=audit_user,
            request=audit_request,
        )

    return AircraftOut.from_orm(aircraft)

async def update_aircraft_with_file(
    session: AsyncSession,
    aircraft_id: int,
    data: AircraftUpdate,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
    *,
    audit_account_id: Optional[int] = None,
):
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == aircraft_id)
    )
    aircraft = result.scalar_one_or_none()

    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    update_data = data.dict(exclude_unset=True)

    # --- Handle engine file ---
    if engine_file:
        update_data["engine_arc"] = await _persist_upload_file(engine_file)

    # --- Handle propeller file ---
    if propeller_file:
        update_data["propeller_arc"] = await _persist_upload_file(propeller_file)

    # --- Uniqueness checks (exclude current aircraft) ---
    if "registration" in update_data:
        if await _find_active_aircraft_by_field(
            session,
            "registration",
            update_data["registration"],
            exclude_id=aircraft_id,
        ):
            raise HTTPException(status_code=400, detail="Registration already exists")

    if "msn" in update_data:
        if await _find_active_aircraft_by_field(
            session,
            "msn",
            update_data["msn"],
            exclude_id=aircraft_id,
        ):
            raise HTTPException(status_code=400, detail="MSN already exists")

    # --- Apply updates ---
    for key, value in update_data.items():
        setattr(aircraft, key, value)
    await _sync_fleet_daily_update_when_aircraft_maintenance(
        session, aircraft, audit_account_id=audit_account_id
    )
    if audit_account_id is not None:
        await set_audit_fields(aircraft, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(aircraft)

    return AircraftOut.from_orm(aircraft)

async def soft_delete_aircraft(
    session: AsyncSession,
    id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete aircraft and all connected data (cascade).
    Sets is_deleted=True on aircraft and all related records in a single transaction.
    """
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    aircraft = result.scalar_one_or_none()
    if not aircraft:
        return False

    aircraft_id = aircraft.id
    old_data_snapshot = serialize_audit_data(aircraft)

    async def _soft_delete_many(model, fk_col, fk_val):
        """Helper: soft delete all non-deleted records for given FK."""
        stmt = select(model).where(fk_col == fk_val).where(model.is_deleted == False)
        r = await session.execute(stmt)
        for obj in r.scalars().all():
            obj.soft_delete()
            session.add(obj)

    # WorkOrderADMonitoring: soft delete work orders for ADs belonging to this aircraft
    ad_stmt = select(ADMonitoring.id).where(
        ADMonitoring.aircraft_fk == aircraft_id
    ).where(ADMonitoring.is_deleted == False)
    ad_ids = [row[0] for row in (await session.execute(ad_stmt)).all()]
    if ad_ids:
        wo_stmt = select(WorkOrderADMonitoring).where(
            WorkOrderADMonitoring.ad_monitoring_fk.in_(ad_ids),
            WorkOrderADMonitoring.is_deleted == False,
        )
        for wo in (await session.execute(wo_stmt)).scalars().all():
            wo.soft_delete()
            session.add(wo)

    # ADMonitoring
    await _soft_delete_many(ADMonitoring, ADMonitoring.aircraft_fk, aircraft_id)
    # LDNDMonitoring
    await _soft_delete_many(LDNDMonitoring, LDNDMonitoring.aircraft_fk, aircraft_id)
    # AircraftTechnicalLog
    await _soft_delete_many(AircraftTechnicalLog, AircraftTechnicalLog.aircraft_fk, aircraft_id)
    # AircraftLogbookEntry
    await _soft_delete_many(AircraftLogbookEntry, AircraftLogbookEntry.aircraft_id, aircraft_id)
    # EngineLogbook, AirframeLogbook, AvionicsLogbook, PropellerLogbook
    await _soft_delete_many(EngineLogbook, EngineLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(AirframeLogbook, AirframeLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(AvionicsLogbook, AvionicsLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(PropellerLogbook, PropellerLogbook.aircraft_fk, aircraft_id)
    # TCCMaintenance
    await _soft_delete_many(TCCMaintenance, TCCMaintenance.aircraft_fk, aircraft_id)
    # DocumentOnBoard
    await _soft_delete_many(DocumentOnBoard, DocumentOnBoard.aircraft_id, aircraft_id)
    # CPCPMonitoring
    await _soft_delete_many(CPCPMonitoring, CPCPMonitoring.aircraft_id, aircraft_id)
    # FleetDailyUpdate (one-to-one with aircraft)
    await _soft_delete_many(FleetDailyUpdate, FleetDailyUpdate.aircraft_fk, aircraft_id)

    # Aircraft
    aircraft.soft_delete()
    session.add(aircraft)
    await _normalize_aircraft_display_order(session)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=aircraft_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def reorder_aircraft(
    session: AsyncSession,
    items: List[AircraftReorderItem],
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AircraftReorderResponse:
    """
    Atomically update Aircraft.display_order for the full active fleet.

    Validates IDs exist and are active, and that the payload is the complete
    active set. Rolls back on any failure. Does not mutate Fleet Daily Update
    business fields.
    """
    validated = validate_reorder_items(items, id_attr="aircraft_id")
    id_to_order = {record_id: order for record_id, order in validated}
    record_ids = list(id_to_order.keys())

    result = await session.execute(
        select(Aircraft)
        .where(Aircraft.id.in_(record_ids))
        .where(Aircraft.is_deleted == False)
    )
    rows = list(result.scalars().all())
    row_map = {row.id: row for row in rows}

    missing_ids = [rid for rid in record_ids if rid not in row_map]
    if missing_ids:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Aircraft record(s) not found: {missing_ids}",
        )

    active_count_result = await session.execute(
        select(func.count())
        .select_from(Aircraft)
        .where(Aircraft.is_deleted == False)
    )
    active_count = int(active_count_result.scalar() or 0)
    if active_count != len(record_ids):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                "Reorder must include every active aircraft "
                f"(expected {active_count} items, got {len(record_ids)})"
            ),
        )

    previous_orders = {row.id: row.display_order for row in rows}

    try:
        # Two-phase update avoids transient unique collisions if a DB constraint is added later.
        for row in rows:
            row.display_order = -row.id
            session.add(row)
            if audit_account_id is not None:
                await set_audit_fields(row, audit_account_id, is_create=False)
        await session.flush()

        for row in rows:
            row.display_order = id_to_order[row.id]
            session.add(row)

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if audit_module_name and audit_table_name:
        new_orders = {row.id: id_to_order[row.id] for row in rows}
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=record_ids[0],
            action=AuditAction.BULK_UPDATE,
            old_data={
                "action": "REORDER",
                "aircraft_ids": record_ids,
                "display_orders": previous_orders,
            },
            new_data={
                "action": "REORDER",
                "aircraft_ids": record_ids,
                "display_orders": new_orders,
            },
            current_user=audit_user,
            request=audit_request,
        )

    ordered_rows = sorted(rows, key=lambda r: (r.display_order, r.id))
    for row in ordered_rows:
        await session.refresh(row)
    return AircraftReorderResponse(
        items=[AircraftOut.from_orm(row) for row in ordered_rows]
    )
