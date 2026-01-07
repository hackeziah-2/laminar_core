from typing import Optional, List, Tuple
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select, or_, cast, String
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.aircraft_logbook_entries import AircraftLogbookEntry
from app.schemas.aircraft_technical_logbook import (
    AircraftLogbookEntryCreate,
    AircraftLogbookEntryUpdate,
    AircraftLogbookEntryRead,
)


async def create_logbook_entry(
    session:AsyncSession,
    data:AircraftLogbookEntryCreate
    ) ->AircraftLogbookEntryRead:

    # Check duplicate sequence_no first
    result = await session.execute(
        select(AircraftLogbookEntry).where(
            AircraftLogbookEntry.sequence_no == data.sequence_no
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="ATL with this Sequence Number already exists"
        )

    # Create + persist
    entry = AircraftLogbookEntry(**data.dict())
    session.add(entry)

    await session.commit()
    await session.refresh(entry)

    return AircraftLogbookEntryRead.from_orm(entry)


async def get_logbook_entry(session: AsyncSession, id: int):
    result = await session.execute(
        select(AircraftLogbookEntry)
        .options(selectinload(AircraftLogbookEntry.aircraft))
        .where(AircraftLogbookEntry.id == id)
    )
    return result.scalar_one_or_none()


async def update_logbook_entry(session: AsyncSession, logbook_entry_id: int, logbook_entry_in: AircraftLogbookEntryUpdate) -> Optional[AircraftLogbookEntryRead]:
    obj = await session.get(AircraftLogbookEntry, logbook_entry_id)
    if not obj:
        return None
    for k, v in logbook_entry_in.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

async def list_aircraft_logbook_entries(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
):
    stmt = (
        select(AircraftLogbookEntry)
        .where(AircraftLogbookEntry.is_deleted == False)
    )

    # 🔍 Search by sequence_no
    if search:
        q = f"%{search}%"
        stmt = stmt.where(AircraftLogbookEntry.sequence_no.ilike(q))

    # ✅ Whitelist sortable fields
    sortable_fields = {
        "created_at": AircraftLogbookEntry.created_at,
        "sequence_no": AircraftLogbookEntry.sequence_no,
        "off_blocks_date": AircraftLogbookEntry.off_blocks_date,
        "on_blocks_date": AircraftLogbookEntry.on_blocks_date,
    }

    # 🔀 Multi-sort logic
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
        # 📌 Default ordering
        stmt = stmt.order_by(
            AircraftLogbookEntry.created_at.desc(),
            AircraftLogbookEntry.sequence_no.asc(),
        )

    # 🔢 Total count (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(AircraftLogbookEntry)
        .where(AircraftLogbookEntry.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            AircraftLogbookEntry.sequence_no.ilike(q)
        )

    total = (await session.execute(count_stmt)).scalar()

    # 📄 Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items, total



async def list_aircraft_has_logbook_entries(
    session: AsyncSession,
    aircraft_id: Optional[int] = None,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
):
    stmt = select(AircraftLogbookEntry)

    # Filter by aircraft
    if aircraft_id:
        stmt = stmt.where(AircraftLogbookEntry.aircraft_id == aircraft_id)

    # Search (safe + useful fields only)
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                AircraftLogbookEntry.sequence_no.ilike(q),
                AircraftLogbookEntry.off_blocks_station.ilike(q),
                AircraftLogbookEntry.on_blocks_station.ilike(q),
                AircraftLogbookEntry.nature_of_flight.ilike(q),
            )
        )

    # Whitelisted sortable fields
    sortable_fields = {
        "sequence_no": AircraftLogbookEntry.sequence_no,
        "off_blocks_date": AircraftLogbookEntry.off_blocks_date,
        "on_blocks_date": AircraftLogbookEntry.on_blocks_date,
        "total_flight_time": AircraftLogbookEntry.total_flight_time,
        "created_at": AircraftLogbookEntry.created_at,
        "updated_at": AircraftLogbookEntry.updated_at,
    }

    # Multi-sort support
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")

            column = sortable_fields.get(field_name)
            if column:
                stmt = stmt.order_by(
                    column.desc() if desc_order else column.asc()
                )
    else:
        stmt = stmt.order_by(AircraftLogbookEntry.off_blocks_date.desc())

    # Count query (same filters, no ORDER BY)
    count_stmt = select(func.count()).select_from(AircraftLogbookEntry)

    if aircraft_id:
        count_stmt = count_stmt.where(
            AircraftLogbookEntry.aircraft_id == aircraft_id
        )

    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                AircraftLogbookEntry.sequence_no.ilike(q),
                AircraftLogbookEntry.off_blocks_station.ilike(q),
                AircraftLogbookEntry.on_blocks_station.ilike(q),
                AircraftLogbookEntry.nature_of_flight.ilike(q),
            )
        )

    total_count = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items, total_count

