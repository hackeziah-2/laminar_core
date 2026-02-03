from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.atl_monitoring import LDNDMonitoring, UnitEnum
from app.schemas.ldnd_monitoring_schema import (
    LDNDMonitoringCreate,
    LDNDMonitoringUpdate,
    LDNDMonitoringRead,
    LDNDLatestResponse,
)


async def get_ldnd_monitoring(
    session: AsyncSession, ldnd_id: int
) -> Optional[LDNDMonitoringRead]:
    """Get a single LDNDMonitoring by ID."""
    result = await session.execute(
        select(LDNDMonitoring)
        .options(selectinload(LDNDMonitoring.aircraft))
        .where(LDNDMonitoring.id == ldnd_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return LDNDMonitoringRead.from_orm(row)


async def get_ldnd_monitoring_by_aircraft(
    session: AsyncSession, ldnd_id: int, aircraft_id: int
) -> Optional[LDNDMonitoringRead]:
    """Get a single LDNDMonitoring by ID, scoped to aircraft_id."""
    result = await session.execute(
        select(LDNDMonitoring)
        .options(selectinload(LDNDMonitoring.aircraft))
        .where(LDNDMonitoring.id == ldnd_id)
        .where(LDNDMonitoring.aircraft_fk == aircraft_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return LDNDMonitoringRead.from_orm(row)


async def get_ldnd_latest_by_aircraft(
    session: AsyncSession, aircraft_id: int
) -> LDNDLatestResponse:
    """Get maintenance summary for aircraft: current tach (from latest-updated record), next inspection, last_updated."""
    # All non-deleted LDND records for this aircraft
    stmt = (
        select(LDNDMonitoring)
        .where(LDNDMonitoring.aircraft_fk == aircraft_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        return LDNDLatestResponse()

    # Latest updated record -> current_tach, last_updated
    rows_with_ts = [r for r in rows if r.updated_at is not None or r.created_at is not None]
    if rows_with_ts:
        latest = max(rows_with_ts, key=lambda r: r.updated_at or r.created_at)
        current_tach = latest.last_done_tach_done
        last_updated = latest.updated_at or latest.created_at
    else:
        latest = rows[0]
        current_tach = latest.last_done_tach_done
        last_updated = None

    # Record with soonest next due (min next_due_tach_hours, excluding nulls)
    with_next = [r for r in rows if r.next_due_tach_hours is not None]
    if with_next:
        next_record = min(with_next, key=lambda r: r.next_due_tach_hours)
        next_inspection_tach_hours = next_record.next_due_tach_hours
        next_inspection_type = next_record.inspection_type
        next_inspection_unit = getattr(next_record.unit, "value", None) or str(next_record.unit) if next_record.unit else None
    else:
        next_inspection_tach_hours = None
        next_inspection_type = None
        next_inspection_unit = None

    return LDNDLatestResponse(
        current_tach=current_tach,
        next_inspection_tach_hours=next_inspection_tach_hours,
        next_inspection_type=next_inspection_type,
        next_inspection_unit=next_inspection_unit,
        last_updated=last_updated,
    )


async def list_ldnd_monitoring(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    aircraft_fk: Optional[int] = None,
    inspection_type: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[LDNDMonitoring], int]:
    """List LDNDMonitoring entries with pagination and filtering."""
    stmt = (
        select(LDNDMonitoring)
        .options(selectinload(LDNDMonitoring.aircraft))
        .where(LDNDMonitoring.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(LDNDMonitoring.aircraft_fk == aircraft_fk)
    if inspection_type and inspection_type.strip():
        stmt = stmt.where(
            LDNDMonitoring.inspection_type.ilike(f"%{inspection_type.strip()}%")
        )

    sortable_fields = {
        "id": LDNDMonitoring.id,
        "aircraft_fk": LDNDMonitoring.aircraft_fk,
        "inspection_type": LDNDMonitoring.inspection_type,
        "unit": LDNDMonitoring.unit,
        "last_done_tach_due": LDNDMonitoring.last_done_tach_due,
        "last_done_tach_done": LDNDMonitoring.last_done_tach_done,
        "next_due_tach_hours": LDNDMonitoring.next_due_tach_hours,
        "performed_date_start": LDNDMonitoring.performed_date_start,
        "performed_date_end": LDNDMonitoring.performed_date_end,
        "created_at": LDNDMonitoring.created_at,
        "updated_at": LDNDMonitoring.updated_at,
    }
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")
            column = sortable_fields.get(field_name)
            if column is not None:
                stmt = stmt.order_by(column.desc() if desc_order else column.asc())
    else:
        stmt = stmt.order_by(LDNDMonitoring.created_at.desc())

    count_stmt = (
        select(func.count())
        .select_from(LDNDMonitoring)
        .where(LDNDMonitoring.is_deleted == False)
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(LDNDMonitoring.aircraft_fk == aircraft_fk)
    if inspection_type and inspection_type.strip():
        count_stmt = count_stmt.where(
            LDNDMonitoring.inspection_type.ilike(f"%{inspection_type.strip()}%")
        )
    total_count = (await session.execute(count_stmt)).scalar()

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total_count


def _unit_to_enum(value: Optional[str]):
    if not value:
        return UnitEnum.HRS
    u = str(value).upper().strip()
    return UnitEnum.CYCLES if u == "CYCLES" else UnitEnum.HRS


async def create_ldnd_monitoring(
    session: AsyncSession, data: LDNDMonitoringCreate
) -> LDNDMonitoringRead:
    """Create a new LDNDMonitoring entry."""
    payload = data.dict()
    payload["unit"] = _unit_to_enum(payload.get("unit")).value
    obj = LDNDMonitoring(**payload)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])
    return LDNDMonitoringRead.from_orm(obj)


async def update_ldnd_monitoring(
    session: AsyncSession, ldnd_id: int, data: LDNDMonitoringUpdate
) -> Optional[LDNDMonitoringRead]:
    """Update an LDNDMonitoring entry."""
    result = await session.execute(
        select(LDNDMonitoring)
        .options(selectinload(LDNDMonitoring.aircraft))
        .where(LDNDMonitoring.id == ldnd_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    update_data = data.dict(exclude_unset=True)
    if "unit" in update_data and update_data["unit"] is not None:
        update_data["unit"] = _unit_to_enum(update_data["unit"]).value
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])
    return LDNDMonitoringRead.from_orm(obj)


async def soft_delete_ldnd_monitoring(
    session: AsyncSession, ldnd_id: int
) -> bool:
    """Soft delete an LDNDMonitoring entry."""
    result = await session.execute(
        select(LDNDMonitoring)
        .where(LDNDMonitoring.id == ldnd_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_ldnd_monitoring_by_aircraft(
    session: AsyncSession, ldnd_id: int, aircraft_id: int
) -> bool:
    """Soft delete an LDNDMonitoring entry, scoped to aircraft_id."""
    result = await session.execute(
        select(LDNDMonitoring)
        .where(LDNDMonitoring.id == ldnd_id)
        .where(LDNDMonitoring.aircraft_fk == aircraft_id)
        .where(LDNDMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
