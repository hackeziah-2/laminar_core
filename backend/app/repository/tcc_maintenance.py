from typing import Optional, List, Tuple

from fastapi import Request
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.tcc_maintenance import TCCMaintenance, MethodOfComplianceEnum, TCCCategoryEnum
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.schemas.tcc_maintenance_schema import (
    TCCMaintenanceCreate,
    TCCMaintenanceUpdate,
    TCCMaintenanceRead,
)
from app.services.tcc_computation import (
    CLIENT_REMAINING_OVERRIDE_KEYS,
    COMPUTED_TCC_COLUMN_KEYS,
    build_computed_tcc_field_values,
    coerce_stored_remaining_override,
)


async def tcc_maintenance_to_read(
    session: AsyncSession,
    obj: TCCMaintenance,
    *,
    prefetched_latest_atl_tach_aftt: Optional[Tuple[Optional[float], Optional[float]]] = None,
) -> TCCMaintenanceRead:
    """ORM row to API read model with next_due_* and remaining_* recomputed from latest aircraft state."""
    read = TCCMaintenanceRead.from_orm(obj)
    computed = await build_computed_tcc_field_values(
        session,
        aircraft_fk=obj.aircraft_fk,
        last_done_date=obj.last_done_date,
        last_done_tach=obj.last_done_tach,
        last_done_aftt=obj.last_done_aftt,
        component_limit_hours=obj.component_limit_hours,
        component_limit_years=obj.component_limit_years,
        prefetched_latest_atl_tach_aftt=prefetched_latest_atl_tach_aftt,
    )
    return read.copy(update=computed)


def _category_from_str(value: Optional[str]) -> Optional[TCCCategoryEnum]:
    """Convert string to TCCCategoryEnum; return None if invalid or None."""
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for e in TCCCategoryEnum:
        if e.value == s or e.name == s:
            return e
    return None


def _method_of_compliance_from_str(value: Optional[str]) -> Optional[MethodOfComplianceEnum]:
    """Convert string to MethodOfComplianceEnum; return None if invalid or None."""
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for e in MethodOfComplianceEnum:
        if e.value == s or e.name == s:
            return e
    return None


async def create_tcc_maintenance(
    session: AsyncSession,
    data: TCCMaintenanceCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> TCCMaintenanceRead:
    """Create a new TCC Maintenance entry."""
    payload = data.dict()
    category_enum = _category_from_str(payload.get("category"))
    component_moc = _method_of_compliance_from_str(payload.get("component_method_of_compliance"))
    last_done_moc = _method_of_compliance_from_str(payload.get("last_done_method_of_compliance"))
    # Store string values for PostgreSQL ENUM (asyncpg compatibility)
    payload["category"] = category_enum.value if category_enum else None
    payload["component_method_of_compliance"] = component_moc.value if component_moc else None
    payload["last_done_method_of_compliance"] = last_done_moc.value if last_done_moc else None

    manual_remaining = {
        k: payload.get(k)
        for k in CLIENT_REMAINING_OVERRIDE_KEYS
        if k in data.__fields_set__
    }
    computed = await build_computed_tcc_field_values(
        session,
        aircraft_fk=payload["aircraft_fk"],
        last_done_date=payload.get("last_done_date"),
        last_done_tach=payload.get("last_done_tach"),
        last_done_aftt=payload.get("last_done_aftt"),
        component_limit_hours=payload.get("component_limit_hours"),
        component_limit_years=payload.get("component_limit_years"),
    )
    payload.update(computed)
    for k, v in manual_remaining.items():
        payload[k] = coerce_stored_remaining_override(k, v)

    obj = TCCMaintenance(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "atl"])

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

    return TCCMaintenanceRead.from_orm(obj)


async def get_tcc_maintenance(
    session: AsyncSession,
    maintenance_id: int,
) -> Optional[TCCMaintenanceRead]:
    """Get a single TCC Maintenance by ID."""
    result = await session.execute(
        select(TCCMaintenance)
        .options(
            selectinload(TCCMaintenance.aircraft),
            selectinload(TCCMaintenance.atl),
        )
        .where(TCCMaintenance.id == maintenance_id)
        .where(TCCMaintenance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return await tcc_maintenance_to_read(session, obj)


async def get_tcc_maintenance_by_aircraft(
    session: AsyncSession,
    maintenance_id: int,
    aircraft_id: int,
) -> Optional[TCCMaintenanceRead]:
    """Get a single TCC Maintenance by ID, scoped to aircraft_id."""
    result = await session.execute(
        select(TCCMaintenance)
        .options(
            selectinload(TCCMaintenance.aircraft),
            selectinload(TCCMaintenance.atl),
        )
        .where(TCCMaintenance.id == maintenance_id)
        .where(TCCMaintenance.aircraft_fk == aircraft_id)
        .where(TCCMaintenance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return await tcc_maintenance_to_read(session, obj)


async def get_latest_tcc_by_aircraft_and_description(
    session: AsyncSession,
    aircraft_id: int,
    description: str,
) -> Optional[TCCMaintenance]:
    """Get the latest TCC for the aircraft with the given description (e.g. 'Engine', 'Propeller').
    'Latest' is by linked ATL sequence_no (TCC.atl_ref -> ATL); TCCs without atl_ref are ordered last."""
    if not description or not str(description).strip():
        return None
    desc_match = str(description).strip()
    stmt = (
        select(TCCMaintenance)
        .outerjoin(
            AircraftTechnicalLog,
            TCCMaintenance.atl_ref == AircraftTechnicalLog.id,
        )
        .where(TCCMaintenance.aircraft_fk == aircraft_id)
        .where(TCCMaintenance.is_deleted == False)
        .where(cast(TCCMaintenance.description, String).ilike(desc_match))
        .order_by(
            AircraftTechnicalLog.sequence_no.desc().nulls_last(),
            TCCMaintenance.id.desc(),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_tcc_maintenances(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    atl_ref: Optional[int] = None,
    category: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[TCCMaintenance], int]:
    """List TCC Maintenance entries with pagination, search, and filters."""
    stmt = (
        select(TCCMaintenance)
        .options(
            selectinload(TCCMaintenance.aircraft),
            selectinload(TCCMaintenance.atl),
        )
        .where(TCCMaintenance.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(TCCMaintenance.aircraft_fk == aircraft_fk)
    if atl_ref is not None:
        stmt = stmt.where(TCCMaintenance.atl_ref == atl_ref)
    if category and str(category).strip():
        cat_str = str(category).strip()
        # If "All" or "All Categories" (case-insensitive), do not filter at all
        if cat_str.lower() in ["all", "all categories"]:
            pass
        else:
            cat_enum = _category_from_str(cat_str)
            if cat_enum is not None:
                stmt = stmt.where(TCCMaintenance.category == cat_enum.value)
            else:
                # User asked for a specific category that is invalid/not found -> return empty result
                stmt = stmt.where(1 == 0)

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                TCCMaintenance.part_number.ilike(q),
                cast(TCCMaintenance.serial_number, String).ilike(q),
                cast(TCCMaintenance.description, String).ilike(q),
            )
        )

    sortable_fields = {
        "id": TCCMaintenance.id,
        "category": TCCMaintenance.category,
        "part_number": TCCMaintenance.part_number,
        "last_done_date": TCCMaintenance.last_done_date,
        "created_at": TCCMaintenance.created_at,
        "updated_at": TCCMaintenance.updated_at,
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
        stmt = stmt.order_by(TCCMaintenance.created_at.desc())

    count_stmt = (
        select(func.count())
        .select_from(TCCMaintenance)
        .where(TCCMaintenance.is_deleted == False)
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(TCCMaintenance.aircraft_fk == aircraft_fk)
    if atl_ref is not None:
        count_stmt = count_stmt.where(TCCMaintenance.atl_ref == atl_ref)
    if category and str(category).strip():
        cat_str = str(category).strip()
        if cat_str.lower() in ["all", "all categories"]:
            pass
        else:
            cat_enum = _category_from_str(category)
            if cat_enum is not None:
                count_stmt = count_stmt.where(TCCMaintenance.category == cat_enum.value)
            else:
                # Invalid category -> return 0 count
                count_stmt = count_stmt.where(1 == 0)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(
            or_(
                TCCMaintenance.part_number.ilike(q),
                cast(TCCMaintenance.serial_number, String).ilike(q),
                cast(TCCMaintenance.description, String).ilike(q),
            )
        )
    total_count = (await session.execute(count_stmt)).scalar()

    if limit > 0:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total_count


async def update_tcc_maintenance(
    session: AsyncSession,
    maintenance_id: int,
    data: TCCMaintenanceUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[TCCMaintenanceRead]:
    """Update a TCC Maintenance entry."""
    result = await session.execute(
        select(TCCMaintenance)
        .options(
            selectinload(TCCMaintenance.aircraft),
            selectinload(TCCMaintenance.atl),
        )
        .where(TCCMaintenance.id == maintenance_id)
        .where(TCCMaintenance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    manual_remaining = {
        k: update_data.pop(k)
        for k in CLIENT_REMAINING_OVERRIDE_KEYS
        if k in update_data
    }
    if "category" in update_data:
        cat = _category_from_str(update_data["category"])
        update_data["category"] = cat.value if cat else None
    if "component_method_of_compliance" in update_data:
        moc = _method_of_compliance_from_str(update_data["component_method_of_compliance"])
        update_data["component_method_of_compliance"] = moc.value if moc else None
    if "last_done_method_of_compliance" in update_data:
        moc = _method_of_compliance_from_str(update_data["last_done_method_of_compliance"])
        update_data["last_done_method_of_compliance"] = moc.value if moc else None

    for k in list(update_data.keys()):
        if k in COMPUTED_TCC_COLUMN_KEYS:
            del update_data[k]

    for k, v in update_data.items():
        setattr(obj, k, v)

    computed = await build_computed_tcc_field_values(
        session,
        aircraft_fk=obj.aircraft_fk,
        last_done_date=obj.last_done_date,
        last_done_tach=obj.last_done_tach,
        last_done_aftt=obj.last_done_aftt,
        component_limit_hours=obj.component_limit_hours,
        component_limit_years=obj.component_limit_years,
    )
    for k, v in computed.items():
        if k in manual_remaining:
            setattr(obj, k, coerce_stored_remaining_override(k, manual_remaining[k]))
        else:
            setattr(obj, k, v)
    for k, v in manual_remaining.items():
        if k not in computed:
            setattr(obj, k, coerce_stored_remaining_override(k, v))

    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "atl"])

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

    return TCCMaintenanceRead.from_orm(obj)


async def soft_delete_tcc_maintenance(
    session: AsyncSession,
    maintenance_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a TCC Maintenance entry."""
    result = await session.execute(
        select(TCCMaintenance)
        .where(TCCMaintenance.id == maintenance_id)
        .where(TCCMaintenance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=maintenance_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def soft_delete_tcc_maintenance_by_aircraft(
    session: AsyncSession,
    maintenance_id: int,
    aircraft_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a TCC Maintenance entry, scoped to aircraft_id."""
    result = await session.execute(
        select(TCCMaintenance)
        .where(TCCMaintenance.id == maintenance_id)
        .where(TCCMaintenance.aircraft_fk == aircraft_id)
        .where(TCCMaintenance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=maintenance_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
