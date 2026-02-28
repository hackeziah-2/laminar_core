from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.aircraft import Aircraft
from app.models.fleet_daily_update import FleetDailyUpdate, FleetDailyUpdateStatusEnum
from app.schemas.fleet_daily_update_schema import (
    FleetDailyUpdateCreate,
    FleetDailyUpdateUpdate,
)


def _status_from_str(value: Optional[str]) -> Optional[str]:
    """Return valid enum value string or None."""
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for e in FleetDailyUpdateStatusEnum:
        if e.value == s or e.name == s:
            return e.value
    return None


async def create_fleet_daily_update(
    session: AsyncSession,
    data: FleetDailyUpdateCreate,
) -> FleetDailyUpdate:
    """Create a new Fleet Daily Update entry. aircraft_fk must be unique (one-to-one). Returns ORM."""
    payload = data.dict(exclude_unset=True)
    status_val = _status_from_str(payload.get("status")) or FleetDailyUpdateStatusEnum.RUNNING.value
    payload["status"] = status_val

    # Enforce one-to-one: one record per aircraft
    existing = await session.execute(
        select(FleetDailyUpdate)
        .where(FleetDailyUpdate.aircraft_fk == payload["aircraft_fk"])
        .where(FleetDailyUpdate.is_deleted == False)
    )
    if existing.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="A Fleet Daily Update already exists for this aircraft.",
        )

    obj = FleetDailyUpdate(**payload)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])
    return obj


async def get_fleet_daily_update(
    session: AsyncSession,
    update_id: int,
) -> Optional[FleetDailyUpdate]:
    """Get a single Fleet Daily Update by ID. Returns ORM with aircraft loaded."""
    result = await session.execute(
        select(FleetDailyUpdate)
        .options(selectinload(FleetDailyUpdate.aircraft))
        .where(FleetDailyUpdate.id == update_id)
        .where(FleetDailyUpdate.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_fleet_daily_update_by_aircraft(
    session: AsyncSession,
    aircraft_id: int,
) -> Optional[FleetDailyUpdate]:
    """Get the Fleet Daily Update for an aircraft (one-to-one). Returns ORM with aircraft loaded."""
    result = await session.execute(
        select(FleetDailyUpdate)
        .options(selectinload(FleetDailyUpdate.aircraft))
        .where(FleetDailyUpdate.aircraft_fk == aircraft_id)
        .where(FleetDailyUpdate.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_fleet_daily_updates(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    status: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[FleetDailyUpdate], int]:
    """List Fleet Daily Update entries with pagination, search by aircraft registration, and filters."""
    stmt = (
        select(FleetDailyUpdate)
        .options(selectinload(FleetDailyUpdate.aircraft))
        .where(FleetDailyUpdate.is_deleted == False)
    )
    count_stmt = (
        select(func.count())
        .select_from(FleetDailyUpdate)
        .where(FleetDailyUpdate.is_deleted == False)
    )

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.join(Aircraft, FleetDailyUpdate.aircraft_fk == Aircraft.id).where(
            Aircraft.is_deleted == False,
            Aircraft.registration.ilike(q),
        )
        count_stmt = count_stmt.join(
            Aircraft, FleetDailyUpdate.aircraft_fk == Aircraft.id
        ).where(
            Aircraft.is_deleted == False,
            Aircraft.registration.ilike(q),
        )
    if aircraft_fk is not None:
        stmt = stmt.where(FleetDailyUpdate.aircraft_fk == aircraft_fk)
        count_stmt = count_stmt.where(FleetDailyUpdate.aircraft_fk == aircraft_fk)
    if status and str(status).strip():
        status_val = _status_from_str(str(status).strip())
        if status_val:
            stmt = stmt.where(FleetDailyUpdate.status == status_val)
            count_stmt = count_stmt.where(FleetDailyUpdate.status == status_val)

    sortable_fields = {
        "id": FleetDailyUpdate.id,
        "aircraft_fk": FleetDailyUpdate.aircraft_fk,
        "status": FleetDailyUpdate.status,
        "created_at": FleetDailyUpdate.created_at,
        "updated_at": FleetDailyUpdate.updated_at,
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
        stmt = stmt.order_by(FleetDailyUpdate.created_at.desc())

    total_count = (await session.execute(count_stmt)).scalar()
    if limit > 0:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total_count


async def update_fleet_daily_update(
    session: AsyncSession,
    update_id: int,
    data: FleetDailyUpdateUpdate,
) -> Optional[FleetDailyUpdate]:
    """Update a Fleet Daily Update entry. Returns ORM with aircraft loaded."""
    result = await session.execute(
        select(FleetDailyUpdate)
        .options(selectinload(FleetDailyUpdate.aircraft))
        .where(FleetDailyUpdate.id == update_id)
        .where(FleetDailyUpdate.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = data.dict(exclude_unset=True)
    if "status" in update_data:
        status_val = _status_from_str(update_data["status"])
        update_data["status"] = status_val if status_val else obj.status

    for k, v in update_data.items():
        if hasattr(obj, k):
            setattr(obj, k, v)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])
    return obj


async def soft_delete_fleet_daily_update(
    session: AsyncSession,
    update_id: int,
) -> bool:
    """Soft delete a Fleet Daily Update entry."""
    result = await session.execute(
        select(FleetDailyUpdate)
        .where(FleetDailyUpdate.id == update_id)
        .where(FleetDailyUpdate.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_fleet_daily_update_by_aircraft(
    session: AsyncSession,
    update_id: int,
    aircraft_id: int,
) -> bool:
    """Soft delete a Fleet Daily Update entry scoped to aircraft_id."""
    result = await session.execute(
        select(FleetDailyUpdate)
        .where(FleetDailyUpdate.id == update_id)
        .where(FleetDailyUpdate.aircraft_fk == aircraft_id)
        .where(FleetDailyUpdate.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
