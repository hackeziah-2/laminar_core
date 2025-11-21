from sqlalchemy import select, or_, cast, String
from fastapi import Query

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftCreate
from typing import List, Optional, Tuple

async def get_aircraft(session: AsyncSession, id: int) -> Optional[Aircraft]:
    return await session.get(Aircraft, id)

async def create_aircraft(session: AsyncSession, aircraft_data: AircraftCreate) -> Aircraft:
    obj = Aircraft(**aircraft_data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

async def list_aircraft(session: AsyncSession, limit: int =0, offset: int=0,
    search: Optional[str]=None, status: Optional[str] = "all"):
    stmt = select(Aircraft)
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(Aircraft.registration.ilike(q),
                (Aircraft.base.ilike(q)),
                (Aircraft.model.ilike(q)),
                (Aircraft.reg_no.ilike(q)),
            )
        )
    
    # Status filter
    if status and status.lower() != "all":
        status_value = f"%{status.strip()}%"
        stmt = stmt.where(cast(Aircraft.status, String).ilike(status_value))
        
    total = await session.execute(select(Aircraft))
    total_count = len(total.scalars().all())
    stmt = stmt.limit(limit).offset(offset)
    res = await session.execute(stmt)
    items = res.scalars().all()
    return items, total_count
