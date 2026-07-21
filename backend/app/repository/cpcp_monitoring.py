from typing import Optional, List, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.cpcp_monitoring import CPCPMonitoring
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.schemas.cpcp_monitoring_schema import (
    CPCPMonitoringCreate,
    CPCPMonitoringUpdate,
    CPCPMonitoringRead,
    CPCPMonitoringReorderItem,
    CPCPMonitoringReorderResponse,
)
from app.services.cpcp_computation import apply_cpcp_next_due_fields, to_cpcp_monitoring_read
from app.services.display_order_reorder import validate_reorder_items


async def create_cpcp_monitoring(
    session: AsyncSession,
    data: CPCPMonitoringCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> CPCPMonitoringRead:
    """Create a new CPCP Monitoring entry."""
    payload = data.dict()
    max_order_result = await session.execute(
        select(func.coalesce(func.max(CPCPMonitoring.display_order), 0)).where(
            CPCPMonitoring.aircraft_id == payload["aircraft_id"],
            CPCPMonitoring.is_deleted == False,
        )
    )
    payload["display_order"] = int(max_order_result.scalar() or 0) + 1

    obj = CPCPMonitoring(**payload)
    apply_cpcp_next_due_fields(obj)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["atl"])

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return await to_cpcp_monitoring_read(session, obj)


async def get_cpcp_monitoring(
    session: AsyncSession,
    entry_id: int,
) -> Optional[CPCPMonitoringRead]:
    """Get a single CPCP Monitoring by ID."""
    result = await session.execute(
        select(CPCPMonitoring)
        .options(selectinload(CPCPMonitoring.atl))
        .where(CPCPMonitoring.id == entry_id)
        .where(CPCPMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return await to_cpcp_monitoring_read(session, obj)


async def list_cpcp_monitorings(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    aircraft_id: Optional[int] = None,
) -> Tuple[List[CPCPMonitoring], int]:
    """List CPCP Monitoring entries with pagination. Search by Description and ATL Sequence NO. Filter by aircraft_id."""
    stmt = (
        select(CPCPMonitoring)
        .options(selectinload(CPCPMonitoring.atl))
        .where(CPCPMonitoring.is_deleted == False)
    )
    if aircraft_id is not None:
        stmt = stmt.where(CPCPMonitoring.aircraft_id == aircraft_id)

    if search and search.strip():
        q = f"%{search.strip()}%"
        # Left outer join ATL so we can search by sequence_no; include rows with no atl_ref (description only)
        stmt = stmt.outerjoin(
            AircraftTechnicalLog,
            (CPCPMonitoring.atl_ref == AircraftTechnicalLog.id) & (AircraftTechnicalLog.is_deleted == False),
        )
        stmt = stmt.where(
            or_(
                cast(CPCPMonitoring.description, String).ilike(q),
                AircraftTechnicalLog.sequence_no.ilike(q),
            )
        ).distinct()

    sortable_fields = {
        "id": CPCPMonitoring.id,
        "inspection_operation": CPCPMonitoring.inspection_operation,
        "last_done_date": CPCPMonitoring.last_done_date,
        "display_order": CPCPMonitoring.display_order,
        "created_at": CPCPMonitoring.created_at,
        "updated_at": CPCPMonitoring.updated_at,
    }
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")
            column = sortable_fields.get(field_name)
            if column is None:
                continue
            stmt = stmt.order_by(column.desc() if desc_order else column.asc())
    else:
        stmt = stmt.order_by(
            CPCPMonitoring.display_order.asc(),
            CPCPMonitoring.id.asc(),
        )

    count_stmt = (
        select(func.count())
        .select_from(CPCPMonitoring)
        .where(CPCPMonitoring.is_deleted == False)
    )
    if aircraft_id is not None:
        count_stmt = count_stmt.where(CPCPMonitoring.aircraft_id == aircraft_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.outerjoin(
            AircraftTechnicalLog,
            (CPCPMonitoring.atl_ref == AircraftTechnicalLog.id) & (AircraftTechnicalLog.is_deleted == False),
        )
        count_stmt = count_stmt.where(
            or_(
                cast(CPCPMonitoring.description, String).ilike(q),
                AircraftTechnicalLog.sequence_no.ilike(q),
            )
        )
    total_count = (await session.execute(count_stmt)).scalar()

    if limit > 0:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return list(items), total_count


async def update_cpcp_monitoring(
    session: AsyncSession,
    entry_id: int,
    data: CPCPMonitoringUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[CPCPMonitoringRead]:
    """Update a CPCP Monitoring entry."""
    result = await session.execute(
        select(CPCPMonitoring)
        .options(selectinload(CPCPMonitoring.atl))
        .where(CPCPMonitoring.id == entry_id)
        .where(CPCPMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)

    apply_cpcp_next_due_fields(obj)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["atl"])

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return await to_cpcp_monitoring_read(session, obj)


async def _normalize_cpcp_display_order_for_aircraft(
    session: AsyncSession,
    aircraft_id: int,
) -> None:
    """Renumber remaining active CPCP rows for an aircraft to 1..N."""
    result = await session.execute(
        select(CPCPMonitoring)
        .where(CPCPMonitoring.aircraft_id == aircraft_id)
        .where(CPCPMonitoring.is_deleted == False)
        .order_by(CPCPMonitoring.display_order.asc(), CPCPMonitoring.id.asc())
    )
    for index, row in enumerate(result.scalars().all(), start=1):
        if row.display_order != index:
            row.display_order = index
            session.add(row)


async def soft_delete_cpcp_monitoring(
    session: AsyncSession,
    entry_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a CPCP Monitoring entry."""
    result = await session.execute(
        select(CPCPMonitoring)
        .where(CPCPMonitoring.id == entry_id)
        .where(CPCPMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    aircraft_id = obj.aircraft_id
    obj.soft_delete()
    session.add(obj)
    await _normalize_cpcp_display_order_for_aircraft(session, aircraft_id)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=entry_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def reorder_cpcp_monitorings(
    session: AsyncSession,
    items: List[CPCPMonitoringReorderItem],
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> CPCPMonitoringReorderResponse:
    """
    Atomically update display_order for CPCP rows belonging to one aircraft.

    Validates IDs exist, share the same aircraft parent, and form the complete
    active set for that aircraft. Rolls back on any failure.
    """
    validated = validate_reorder_items(items)
    id_to_order = {record_id: order for record_id, order in validated}
    record_ids = list(id_to_order.keys())

    result = await session.execute(
        select(CPCPMonitoring)
        .options(selectinload(CPCPMonitoring.atl))
        .where(CPCPMonitoring.id.in_(record_ids))
        .where(CPCPMonitoring.is_deleted == False)
    )
    rows = list(result.scalars().all())
    row_map = {row.id: row for row in rows}

    missing_ids = [rid for rid in record_ids if rid not in row_map]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CPCP Monitoring record(s) not found: {missing_ids}",
        )

    aircraft_ids = {row.aircraft_id for row in rows}
    if len(aircraft_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All CPCP records in a reorder must belong to the same aircraft",
        )
    aircraft_id = next(iter(aircraft_ids))

    active_count_result = await session.execute(
        select(func.count())
        .select_from(CPCPMonitoring)
        .where(CPCPMonitoring.aircraft_id == aircraft_id)
        .where(CPCPMonitoring.is_deleted == False)
    )
    active_count = int(active_count_result.scalar() or 0)
    if active_count != len(record_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Reorder must include every active CPCP record for the aircraft "
                f"(expected {active_count} items, got {len(record_ids)})"
            ),
        )

    old_data_snapshots = {row.id: serialize_audit_data(row) for row in rows}

    try:
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if audit_module_name and audit_table_name:
        for row in rows:
            await session.refresh(row)
            await create_audit_log(
                db=session,
                module_name=audit_module_name,
                table_name=audit_table_name,
                record_id=row.id,
                action=AuditAction.UPDATE,
                old_data=old_data_snapshots.get(row.id),
                new_data=row,
                current_user=audit_user,
                request=audit_request,
            )

    ordered_rows = sorted(rows, key=lambda r: (r.display_order, r.id))
    return CPCPMonitoringReorderResponse(
        items=[CPCPMonitoringRead.from_orm(row) for row in ordered_rows]
    )
