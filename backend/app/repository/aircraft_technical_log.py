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

def generate_range(start_id: str, end_id: str) -> list[str]:
    """
    Generate a list of sequence IDs between start_id and end_id (exclusive).
    Example: ATL-0001 -> ATL-0008 returns ATL-0002 to ATL-0007
    """
    prefix, start_num_str = start_id.split('-')
    _, end_num_str = end_id.split('-')

    start_num = int(start_num_str)
    end_num = int(end_num_str)
    width = len(start_num_str)

    return [f"{prefix}-{str(i).zfill(width)}" for i in range(start_num + 1, end_num)]


async def create_aircraft_technical_log(
    session: AsyncSession,
    data: AircraftTechnicalLogCreate
) -> AircraftTechnicalLogRead:
    """Create a new Aircraft Technical Log entry with optional gap-fill (skipped when first ATL for aircraft)."""

    # Check for duplicate sequence_no
    existing = await session.scalar(
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.sequence_no == data.sequence_no)
        .where(AircraftTechnicalLog.aircraft_fk == data.aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Sequence No. {data.sequence_no} already exists. Please use a different Sequence No."
        )

    # Prepare log data dictionary
    log_data = data.dict(exclude={'component_parts'})
    nf = log_data.get('nature_of_flight')
    if nf is None or (isinstance(nf, str) and (not str(nf).strip() or str(nf).strip() == "-")):
        log_data['nature_of_flight'] = None
    elif isinstance(nf, str):
        log_data['nature_of_flight'] = TypeEnum(nf)

    # Get latest ATL for this aircraft (for hobbs/tach and for gap detection)
    latest_stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == data.aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .order_by(AircraftTechnicalLog.sequence_no.desc())
        .limit(1)
    )
    latest_result = await session.execute(latest_stmt)
    latest_atl = latest_result.scalar_one_or_none()
    latest_sequence_no = latest_atl.sequence_no if latest_atl else None

    # Auto-populate hobbs_meter_start and tachometer_start from latest ATL, or 0 for first entry
    if log_data.get('hobbs_meter_start') is None or log_data.get('tachometer_start') is None:
        if latest_atl:
            if log_data.get('hobbs_meter_start') is None:
                log_data['hobbs_meter_start'] = latest_atl.hobbs_meter_end
            if log_data.get('tachometer_start') is None:
                log_data['tachometer_start'] = latest_atl.tachometer_end
        else:
            if log_data.get('hobbs_meter_start') is None:
                log_data['hobbs_meter_start'] = 0.0
            if log_data.get('tachometer_start') is None:
                log_data['tachometer_start'] = 0.0

    # Create the main ATL entry (use model, not schema)
    entry = AircraftTechnicalLog(**{**log_data, 'sequence_no': data.sequence_no})
    session.add(entry)
    await session.flush()

    # Generate missing sequence IDs only when there is existing data (skip when first ATL for aircraft)
    if latest_sequence_no is not None:
        try:
            missing_sequences = generate_range(latest_sequence_no, data.sequence_no)
        except (ValueError, IndexError):
            missing_sequences = []
        if missing_sequences:
            for seq_no in missing_sequences:
                gap_entry = AircraftTechnicalLog(sequence_no=seq_no, aircraft_fk=data.aircraft_fk)
                session.add(gap_entry)
                await session.flush()

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

def _normalize_atl_search(search: str) -> str:
    """Normalize ATL sequence search: strip and optionally remove leading 'ATL-' so 'ATL-24451' or '24451' both match."""
    s = str(search).strip()
    if not s:
        return s
    if s.upper().startswith("ATL-"):
        s = s[4:].strip() or s
    return s


async def search_atl_by_sequence_no(
    session: AsyncSession,
    search: str,
    aircraft_fk: Optional[int] = None,
    limit: int = 50,
) -> List[AircraftTechnicalLog]:
    """Search Aircraft Technical Log by ATL Sequence Number. Optionally filter by aircraft. Returns list with aircraft loaded. Accepts 'ATL-24451' or '24451'."""
    if not search or not str(search).strip():
        return []
    normalized = _normalize_atl_search(search)
    q = f"%{normalized}%"
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
    
    # nature_of_flight is optional; None, empty string, or "-" -> None
    if 'nature_of_flight' in update_data:
        nf = update_data['nature_of_flight']
        if nf is None or (isinstance(nf, str) and (not str(nf).strip() or str(nf).strip() == "-")):
            update_data['nature_of_flight'] = None
        elif isinstance(nf, str):
            update_data['nature_of_flight'] = TypeEnum(nf)

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


async def get_previous_atl(
    session: AsyncSession,
    aircraft_fk: int,
    sequence_no: str,
) -> Optional[AircraftTechnicalLog]:
    """Get the previous ATL for the same aircraft: the row with the latest sequence_no that is less than the given sequence_no (immediate predecessor by sequence order). Used for auto_comp 'Previous' values. Excludes soft-deleted."""
    stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(AircraftTechnicalLog.sequence_no < sequence_no)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .order_by(AircraftTechnicalLog.sequence_no.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_atl_paged(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    nature_of_flight: Optional[str] = None,
    sort_sequence: str = "asc",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[AircraftTechnicalLog], int]:
    """List ATL entries for /api/v1/aircraft/{aircraft_id}/atl/paged: search by sequence_no, filter by nature_of_flight, sort by sequence_no, always filter by aircraft_fk when provided."""
    # Exclude soft-deleted ATL (is_deleted = True must not be included); exclude ATLs whose aircraft is soft-deleted
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
    )
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    if search and str(search).strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(AircraftTechnicalLog.sequence_no.ilike(q))
    if nature_of_flight and str(nature_of_flight).strip():
        try:
            nf = TypeEnum(nature_of_flight.strip().upper().replace(" ", "_"))
            stmt = stmt.where(AircraftTechnicalLog.nature_of_flight == nf)
        except ValueError:
            pass
    if sort_sequence.lower() == "desc":
        stmt = stmt.order_by(AircraftTechnicalLog.sequence_no.desc())
    else:
        stmt = stmt.order_by(AircraftTechnicalLog.sequence_no.asc())

    count_stmt = (
        select(func.count())
        .select_from(AircraftTechnicalLog)
        .join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    if search and str(search).strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(AircraftTechnicalLog.sequence_no.ilike(q))
    if nature_of_flight and str(nature_of_flight).strip():
        try:
            nf = TypeEnum(nature_of_flight.strip().upper().replace(" ", "_"))
            count_stmt = count_stmt.where(AircraftTechnicalLog.nature_of_flight == nf)
        except ValueError:
            pass

    total = (await session.execute(count_stmt)).scalar()
    total = int(total) if total is not None else 0
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


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

    # Whitelist sortable fields (includes new run_time, tsn, tbo, life_limits)
    sortable_fields = {
        "created_at": AircraftTechnicalLog.created_at,
        "updated_at": AircraftTechnicalLog.updated_at,
        "sequence_no": AircraftTechnicalLog.sequence_no,
        "origin_date": AircraftTechnicalLog.origin_date,
        "destination_date": AircraftTechnicalLog.destination_date,
        "origin_station": AircraftTechnicalLog.origin_station,
        "destination_station": AircraftTechnicalLog.destination_station,
        "airframe_run_time": AircraftTechnicalLog.airframe_run_time,
        "airframe_aftt": AircraftTechnicalLog.airframe_aftt,
        "engine_run_time": AircraftTechnicalLog.engine_run_time,
        "engine_tsn": AircraftTechnicalLog.engine_tsn,
        "engine_tso": AircraftTechnicalLog.engine_tso,
        "engine_tbo": AircraftTechnicalLog.engine_tbo,
        "propeller_run_time": AircraftTechnicalLog.propeller_run_time,
        "propeller_tsn": AircraftTechnicalLog.propeller_tsn,
        "propeller_tso": AircraftTechnicalLog.propeller_tso,
        "propeller_tbo": AircraftTechnicalLog.propeller_tbo,
        "life_time_limit_engine": AircraftTechnicalLog.life_time_limit_engine,
        "life_time_limit_propeller": AircraftTechnicalLog.life_time_limit_propeller,
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
