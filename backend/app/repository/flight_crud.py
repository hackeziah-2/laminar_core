from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.flight import Flight
from app.schemas.flight_schema import FlightCreate, FlightUpdate
from typing import List, Optional, Tuple

async def get_flight(session: AsyncSession, flight_id: int) -> Optional[Flight]:
    return await session.get(Flight, flight_id)

async def create_flight(session: AsyncSession, flight_in: FlightCreate) -> Flight:
    
    if flight_in.departure_time and flight_in.departure_time.tzinfo is not None:
        flight_in.departure_time = flight_in.departure_time.replace(tzinfo=None)

    if flight_in.arrival_time and flight_in.arrival_time.tzinfo is not None:
        flight_in.arrival_time = flight_in.arrival_time.replace(tzinfo=None)

    obj = Flight(**flight_in.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

async def update_flight(session: AsyncSession, flight_id: int, flight_in: FlightUpdate) -> Optional[Flight]:
    obj = await session.get(Flight, flight_id)
    if not obj:
        return None
    for k, v in flight_in.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
    
async def delete_flight(session: AsyncSession, flight_id: int) -> bool:
    obj = await session.get(Flight, flight_id)
    if not obj:
        return False
    await session.delete(obj)
    await session.commit()
    return True

async def list_flights(session: AsyncSession, limit: int = 10, offset: int = 0, search: Optional[str] = None) -> Tuple[List[Flight], int]:
    stmt = select(Flight)
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            (Flight.flight_no.ilike(q)) |
            (Flight.origin.ilike(q)) |
            (Flight.destination.ilike(q)) |
            (Flight.status.ilike(q))
        )
    total = await session.execute(select(Flight))
    total_count = len(total.scalars().all())
    stmt = stmt.limit(limit).offset(offset)
    res = await session.execute(stmt)
    items = res.scalars().all()
    return items, total_count
