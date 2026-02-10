from typing import Optional, List, Tuple

from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tcc_maintenance import TCCMaintenance, MethodOfComplianceEnum, TCCCategoryEnum
from app.schemas.tcc_maintenance_schema import (
    TCCMaintenanceCreate,
    TCCMaintenanceUpdate,
    TCCMaintenanceRead,
)


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

    obj = TCCMaintenance(**payload)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "atl"])
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
    return TCCMaintenanceRead.from_orm(obj)


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
    return TCCMaintenanceRead.from_orm(obj)


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
        cat_enum = _category_from_str(category)
        if cat_enum is not None:
            stmt = stmt.where(TCCMaintenance.category == cat_enum.value)

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
        cat_enum = _category_from_str(category)
        if cat_enum is not None:
            count_stmt = count_stmt.where(TCCMaintenance.category == cat_enum.value)
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

    update_data = data.dict(exclude_unset=True)
    if "category" in update_data:
        cat = _category_from_str(update_data["category"])
        update_data["category"] = cat.value if cat else None
    if "component_method_of_compliance" in update_data:
        moc = _method_of_compliance_from_str(update_data["component_method_of_compliance"])
        update_data["component_method_of_compliance"] = moc.value if moc else None
    if "last_done_method_of_compliance" in update_data:
        moc = _method_of_compliance_from_str(update_data["last_done_method_of_compliance"])
        update_data["last_done_method_of_compliance"] = moc.value if moc else None

    for k, v in update_data.items():
        setattr(obj, k, v)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "atl"])
    return TCCMaintenanceRead.from_orm(obj)


async def soft_delete_tcc_maintenance(
    session: AsyncSession,
    maintenance_id: int,
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
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_tcc_maintenance_by_aircraft(
    session: AsyncSession,
    maintenance_id: int,
    aircraft_id: int,
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
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
