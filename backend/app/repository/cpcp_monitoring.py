from typing import Optional, List, Tuple

from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cpcp_monitoring import CPCPMonitoring
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.schemas.cpcp_monitoring_schema import (
    CPCPMonitoringCreate,
    CPCPMonitoringUpdate,
    CPCPMonitoringRead,
)


async def create_cpcp_monitoring(
    session: AsyncSession,
    data: CPCPMonitoringCreate,
) -> CPCPMonitoringRead:
    """Create a new CPCP Monitoring entry."""
    obj = CPCPMonitoring(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["atl"])
    return CPCPMonitoringRead.from_orm(obj)


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
    return CPCPMonitoringRead.from_orm(obj)


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
        stmt = stmt.order_by(CPCPMonitoring.created_at.desc())

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

    update_data = data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["atl"])
    return CPCPMonitoringRead.from_orm(obj)


async def soft_delete_cpcp_monitoring(
    session: AsyncSession,
    entry_id: int,
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
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
