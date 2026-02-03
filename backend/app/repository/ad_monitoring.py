from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ad_monitoring import ADMonitoring, WorkOrderADMonitoring
from app.schemas.ad_monitoring_schema import (
    ADMonitoringCreate,
    ADMonitoringUpdate,
    ADMonitoringRead,
    WorkOrderADMonitoringCreate,
    WorkOrderADMonitoringUpdate,
    WorkOrderADMonitoringRead,
)


# ---------- ADMonitoring ----------
async def get_ad_monitoring(
    session: AsyncSession, ad_id: int
) -> Optional[ADMonitoringRead]:
    """Get a single ADMonitoring by ID."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return ADMonitoringRead.from_orm(row)


async def get_ad_monitoring_by_aircraft(
    session: AsyncSession, ad_id: int, aircraft_id: int
) -> Optional[ADMonitoringRead]:
    """Get a single ADMonitoring by ID, scoped to aircraft_id."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.aircraft_fk == aircraft_id)
        .where(ADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return ADMonitoringRead.from_orm(row)


async def list_ad_monitoring(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    aircraft_fk: Optional[int] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[ADMonitoring], int]:
    """List ADMonitoring with pagination and filtering."""
    stmt = (
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.is_deleted == False)
    )
    if aircraft_fk is not None:
        stmt = stmt.where(ADMonitoring.aircraft_fk == aircraft_fk)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            ADMonitoring.ad_number.ilike(q)
            | ADMonitoring.subject.ilike(q)
            | ADMonitoring.inspection_interval.ilike(q)
        )

    sortable = {
        "id": ADMonitoring.id,
        "aircraft_fk": ADMonitoring.aircraft_fk,
        "ad_number": ADMonitoring.ad_number,
        "subject": ADMonitoring.subject,
        "compli_date": ADMonitoring.compli_date,
        "created_at": ADMonitoring.created_at,
        "updated_at": ADMonitoring.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(ADMonitoring.created_at.desc())

    count_stmt = (
        select(func.count())
        .select_from(ADMonitoring)
        .where(ADMonitoring.is_deleted == False)
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(ADMonitoring.aircraft_fk == aircraft_fk)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(
            ADMonitoring.ad_number.ilike(q)
            | ADMonitoring.subject.ilike(q)
            | ADMonitoring.inspection_interval.ilike(q)
        )
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def create_ad_monitoring(
    session: AsyncSession, data: ADMonitoringCreate
) -> ADMonitoringRead:
    """Create ADMonitoring."""
    obj = ADMonitoring(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "ad_works"])
    return ADMonitoringRead.from_orm(obj)


async def update_ad_monitoring(
    session: AsyncSession, ad_id: int, data: ADMonitoringUpdate
) -> Optional[ADMonitoringRead]:
    """Update ADMonitoring."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft", "ad_works"])
    return ADMonitoringRead.from_orm(obj)


async def soft_delete_ad_monitoring(
    session: AsyncSession, ad_id: int
) -> bool:
    """Soft delete ADMonitoring."""
    result = await session.execute(
        select(ADMonitoring)
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_ad_monitoring_by_aircraft(
    session: AsyncSession, ad_id: int, aircraft_id: int
) -> bool:
    """Soft delete ADMonitoring scoped to aircraft_id."""
    result = await session.execute(
        select(ADMonitoring)
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.aircraft_fk == aircraft_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


# ---------- WorkOrderADMonitoring ----------
def _work_order_select():
    """Base select for WorkOrderADMonitoring with ad_monitoring loaded."""
    return select(WorkOrderADMonitoring).options(
        selectinload(WorkOrderADMonitoring.ad_monitoring)
    )


async def get_work_order_ad_monitoring(
    session: AsyncSession, work_order_id: int
) -> Optional[WorkOrderADMonitoringRead]:
    """Get a single WorkOrderADMonitoring by ID."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return WorkOrderADMonitoringRead.from_orm(row)


async def get_work_order_ad_monitoring_by_ad(
    session: AsyncSession, work_order_id: int, ad_monitoring_id: int
) -> Optional[WorkOrderADMonitoringRead]:
    """Get WorkOrderADMonitoring by ID scoped to ad_monitoring_id."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return WorkOrderADMonitoringRead.from_orm(row)


async def list_work_order_ad_monitoring(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    ad_monitoring_fk: Optional[int] = None,
    sort: Optional[str] = "",
) -> Tuple[List[WorkOrderADMonitoring], int]:
    """List WorkOrderADMonitoring with optional filter by ad_monitoring_fk."""
    stmt = _work_order_select().where(WorkOrderADMonitoring.is_deleted == False)
    if ad_monitoring_fk is not None:
        stmt = stmt.where(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_fk)

    sortable = {
        "id": WorkOrderADMonitoring.id,
        "ad_monitoring_fk": WorkOrderADMonitoring.ad_monitoring_fk,
        "work_order_number": WorkOrderADMonitoring.work_order_number,
        "last_done_actt": WorkOrderADMonitoring.last_done_actt,
        "last_done_tach": WorkOrderADMonitoring.last_done_tach,
        "last_done_date": WorkOrderADMonitoring.last_done_date,
        "next_done_actt": WorkOrderADMonitoring.next_done_actt,
        "tach": WorkOrderADMonitoring.tach,
        "atl_ref": WorkOrderADMonitoring.atl_ref,
        "created_at": WorkOrderADMonitoring.created_at,
        "updated_at": WorkOrderADMonitoring.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(WorkOrderADMonitoring.created_at.desc())

    count_stmt = (
        select(func.count())
        .select_from(WorkOrderADMonitoring)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    if ad_monitoring_fk is not None:
        count_stmt = count_stmt.where(
            WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_fk
        )
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def create_work_order_ad_monitoring(
    session: AsyncSession, data: WorkOrderADMonitoringCreate
) -> WorkOrderADMonitoringRead:
    """Create WorkOrderADMonitoring."""
    obj = WorkOrderADMonitoring(**data.dict())
    session.add(obj)
    await session.commit()
    # Re-fetch with relationship loaded to avoid lazy load in from_orm (async session)
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == obj.id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    assert row is not None, "Work order just created"
    return WorkOrderADMonitoringRead.from_orm(row)


async def update_work_order_ad_monitoring(
    session: AsyncSession, work_order_id: int, data: WorkOrderADMonitoringUpdate
) -> Optional[WorkOrderADMonitoringRead]:
    """Update WorkOrderADMonitoring by ID."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    # Re-fetch with relationship loaded to avoid lazy load in from_orm (async session)
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    return WorkOrderADMonitoringRead.from_orm(row) if row else None


async def soft_delete_work_order_ad_monitoring(
    session: AsyncSession, work_order_id: int
) -> bool:
    """Soft delete WorkOrderADMonitoring by ID."""
    result = await session.execute(
        select(WorkOrderADMonitoring)
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_work_order_ad_monitoring_by_ad(
    session: AsyncSession, work_order_id: int, ad_monitoring_id: int
) -> bool:
    """Soft delete WorkOrderADMonitoring by ID scoped to ad_monitoring_id."""
    result = await session.execute(
        select(WorkOrderADMonitoring)
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
