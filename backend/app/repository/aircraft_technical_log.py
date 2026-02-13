from typing import Optional, List, Tuple
from datetime import date, time

from fastapi import HTTPException
from sqlalchemy import select, or_, cast, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.aircraft_techinical_log import (
    AircraftTechnicalLog,
    ComponentPartsRecord,
    TypeEnum
)
from app.models.aircraft import Aircraft
from app.schemas.aircraft_technical_log_schema import (
    AircraftTechnicalLogCreate,
    AircraftTechnicalLogUpdate,
    AircraftTechnicalLogRead,
    ComponentPartsRecordCreate,
)


async def create_aircraft_technical_log(
    session: AsyncSession,
    data: AircraftTechnicalLogCreate
) -> AircraftTechnicalLogRead:
    """Create a new Aircraft Technical Log entry."""
    # Check duplicate sequence_no (only check non-deleted records)
    result = await session.execute(
        select(AircraftTechnicalLog).where(
            AircraftTechnicalLog.sequence_no == data.sequence_no
        ).where(
            AircraftTechnicalLog.is_deleted == False
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Sequence No. {data.sequence_no} already exists. Please use a different Sequence No."
        )

    # Convert enum string to enum if needed
    log_data = data.dict(exclude={'component_parts'})
    if isinstance(log_data.get('nature_of_flight'), str):
        log_data['nature_of_flight'] = TypeEnum(log_data['nature_of_flight'])

    # Auto-populate hobbs_meter_start and tachometer_start from latest ATL if not provided
    if log_data.get('hobbs_meter_start') is None or log_data.get('tachometer_start') is None:
        # Get the latest ATL entry for this aircraft
        latest_stmt = (
            select(AircraftTechnicalLog)
            .where(AircraftTechnicalLog.aircraft_fk == data.aircraft_fk)
            .where(AircraftTechnicalLog.is_deleted == False)
            .order_by(AircraftTechnicalLog.sequence_no.desc())
            .limit(1)
        )
        latest_result = await session.execute(latest_stmt)
        latest_atl = latest_result.scalar_one_or_none()

        if latest_atl:
            # Use end values from previous entry as start values for new entry
            if log_data.get('hobbs_meter_start') is None:
                log_data['hobbs_meter_start'] = latest_atl.hobbs_meter_end
            if log_data.get('tachometer_start') is None:
                log_data['tachometer_start'] = latest_atl.tachometer_end
        else:
            # No previous entry exists, require these fields
            if log_data.get('hobbs_meter_start') is None:
                raise HTTPException(
                    status_code=400,
                    detail="hobbs_meter_start is required for the first ATL entry of this aircraft"
                )
            if log_data.get('tachometer_start') is None:
                raise HTTPException(
                    status_code=400,
                    detail="tachometer_start is required for the first ATL entry of this aircraft"
                )

    # Create main log entry
    entry = AircraftTechnicalLog(**log_data)
    session.add(entry)
    await session.flush()  # Flush to get the ID

    # Create component parts if provided
    if data.component_parts:
        for part_data in data.component_parts:
            part = ComponentPartsRecord(
                atl_fk=entry.id,
                **part_data.dict()
            )
            session.add(part)

    await session.commit()
    await session.refresh(entry)
    await session.refresh(entry, ['aircraft', 'component_parts'])

    return AircraftTechnicalLogRead.from_orm(entry)


async def search_atl_by_sequence_no(
    session: AsyncSession,
    search: str,
    aircraft_fk: Optional[int] = None,
    limit: int = 50,
) -> List[AircraftTechnicalLog]:
    """Search Aircraft Technical Log by ATL Sequence Number. Optionally filter by aircraft. Returns list with aircraft loaded."""
    if not search or not str(search).strip():
        return []
    q = f"%{str(search).strip()}%"
    stmt = (
        select(AircraftTechnicalLog)
        .options(selectinload(AircraftTechnicalLog.aircraft))
        .where(AircraftTechnicalLog.is_deleted == False)
        .where(AircraftTechnicalLog.sequence_no.ilike(q))
        .order_by(AircraftTechnicalLog.sequence_no.asc())
        .limit(limit)
    )
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_aircraft_technical_log(
    session: AsyncSession,
    id: int
) -> Optional[AircraftTechnicalLogRead]:
    """Get an Aircraft Technical Log entry by ID."""
    result = await session.execute(
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.id == id)
        .where(AircraftTechnicalLog.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AircraftTechnicalLogRead.from_orm(obj)


async def update_aircraft_technical_log(
    session: AsyncSession,
    log_id: int,
    log_in: AircraftTechnicalLogUpdate
) -> Optional[AircraftTechnicalLogRead]:
    """Update an Aircraft Technical Log entry."""
    obj = await session.get(AircraftTechnicalLog, log_id)
    if not obj or obj.is_deleted:
        return None

    # Update main fields
    update_data = log_in.dict(exclude_unset=True, exclude={'component_parts'})
    
    # Remove hobbs_meter_start and tachometer_start from updates (read-only fields)
    update_data.pop('hobbs_meter_start', None)
    update_data.pop('tachometer_start', None)
    
    # Handle enum conversion
    if 'nature_of_flight' in update_data and isinstance(update_data['nature_of_flight'], str):
        update_data['nature_of_flight'] = TypeEnum(update_data['nature_of_flight'])

    for k, v in update_data.items():
        setattr(obj, k, v)

    # Handle component parts update if provided
    if log_in.component_parts is not None:
        # Remove existing parts
        existing_parts_result = await session.execute(
            select(ComponentPartsRecord).where(
                ComponentPartsRecord.atl_fk == log_id
            )
        )
        existing_parts = existing_parts_result.scalars().all()
        for part in existing_parts:
            await session.delete(part)

        # Add new parts
        for part_data in log_in.component_parts:
            part = ComponentPartsRecord(
                atl_fk=log_id,
                **part_data.dict()
            )
            session.add(part)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ['aircraft', 'component_parts'])

    return AircraftTechnicalLogRead.from_orm(obj)


async def list_aircraft_technical_logs(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    sort: Optional[str] = "",
) -> Tuple[List[AircraftTechnicalLog], int]:
    """List Aircraft Technical Log entries with pagination."""
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.is_deleted == False)
    )

    # Filter by aircraft
    if aircraft_fk:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)

    # Search functionality
    if search:
        q = f"%{search}%"
        # Join Aircraft table for registration search
        stmt = stmt.join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        stmt = stmt.where(Aircraft.is_deleted == False)
        stmt = stmt.where(
            or_(
                AircraftTechnicalLog.sequence_no.ilike(q),
                AircraftTechnicalLog.origin_station.ilike(q),
                AircraftTechnicalLog.destination_station.ilike(q),
                cast(AircraftTechnicalLog.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    # Whitelist sortable fields
    sortable_fields = {
        "created_at": AircraftTechnicalLog.created_at,
        "updated_at": AircraftTechnicalLog.updated_at,
        "sequence_no": AircraftTechnicalLog.sequence_no,
        "origin_date": AircraftTechnicalLog.origin_date,
        "destination_date": AircraftTechnicalLog.destination_date,
        "origin_station": AircraftTechnicalLog.origin_station,
        "destination_station": AircraftTechnicalLog.destination_station,
    }

    # Multi-sort logic
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")

            column = sortable_fields.get(field_name)
            if column is None:
                continue

            stmt = stmt.order_by(
                column.desc() if desc_order else column.asc()
            )
    else:
        # Default ordering
        stmt = stmt.order_by(
            AircraftTechnicalLog.created_at.desc(),
            AircraftTechnicalLog.sequence_no.asc(),
        )

    # Total count query (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.is_deleted == False)
    )

    if aircraft_fk:
        count_stmt = count_stmt.where(
            AircraftTechnicalLog.aircraft_fk == aircraft_fk
        )

    if search:
        q = f"%{search}%"
        # Join Aircraft table for registration search in count query
        count_stmt = count_stmt.join(
            Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id
        )
        count_stmt = count_stmt.where(Aircraft.is_deleted == False)
        count_stmt = count_stmt.where(
            or_(
                AircraftTechnicalLog.sequence_no.ilike(q),
                AircraftTechnicalLog.origin_station.ilike(q),
                AircraftTechnicalLog.destination_station.ilike(q),
                cast(AircraftTechnicalLog.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items, total


async def get_latest_aircraft_technical_log(
    session: AsyncSession,
    aircraft_fk: Optional[int] = None
) -> Optional[AircraftTechnicalLogRead]:
    """Get the latest Aircraft Technical Log entry by sequence_no."""
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.is_deleted == False)
    )
    
    # Filter by aircraft if provided
    if aircraft_fk:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    
    # Order by sequence_no descending to get the latest
    stmt = stmt.order_by(AircraftTechnicalLog.sequence_no.desc())
    
    # Get the first result
    stmt = stmt.limit(1)
    
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    
    if not obj:
        return None
    
    return AircraftTechnicalLogRead.from_orm(obj)


async def soft_delete_aircraft_technical_log(
    session: AsyncSession,
    log_id: int
) -> bool:
    """Soft delete an Aircraft Technical Log entry."""
    obj = await session.get(AircraftTechnicalLog, log_id)
    if not obj or obj.is_deleted:
        return False

    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
