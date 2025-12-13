import os

from sqlalchemy import select, or_, cast, String
from sqlalchemy.sql import func
from fastapi import Query, Depends, UploadFile, File, Form, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftCreate, AircraftOut, AircraftUpdate
from typing import List, Optional, Tuple

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  

async def get_aircraft(session: AsyncSession, id: int) -> Optional[AircraftOut]:
    return await session.get(Aircraft, id)

async def list_aircraft(session: AsyncSession, limit: int =0, offset: int=0,
    search: Optional[str]=None, status: Optional[str] = "all"):
    stmt = select(Aircraft)
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(Aircraft.registration.ilike(q),
                (Aircraft.base.ilike(q)),
                (Aircraft.model.ilike(q)),
            )
        )
    
    # Status filter
    if status and status.lower() != "all":
        stmt = stmt.where(func.lower(cast(Aircraft.status, String)) == status.lower())
        
    total = await session.execute(select(Aircraft).order_by(Aircraft.created_at.asc()))
    total_count = len(total.scalars().all())
    stmt = stmt.limit(limit).offset(offset)
    res = await session.execute(stmt)
    items = res.scalars().all()
    return items, total_count


async def update_aircraft(session: AsyncSession, aircraft_id: int, aircraft_in: AircraftUpdate) -> Optional[Aircraft]:
    obj = await session.get(Aircraft, aircraft_id)
    if not obj:
        return None
    for k, v in aircraft_in.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

async def create_aircraft_with_file(
    session: AsyncSession,
    data: AircraftCreate,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
):  
    engine_path = None
    if engine_file:
        engine_path = os.path.join(UPLOAD_DIR, engine_file.filename)
        with open(engine_path, "wb") as f:
            f.write(await engine_file.read())

    propeller_path = None
    if propeller_file:
        propeller_path = os.path.join(UPLOAD_DIR, propeller_file.filename)
        with open(propeller_path, "wb") as f:
            f.write(await propeller_file.read())

    aircraft_data = data.dict()

    if engine_path:
        aircraft_data["engine_arc"] = engine_path

    if propeller_path:
        aircraft_data["propeller_arc"] = propeller_path

    result = await session.execute(
        select(Aircraft).where(Aircraft.registration == aircraft_data["registration"])
    )
    registration_exist = result.scalar_one_or_none()
    if registration_exist:
        raise HTTPException(status_code=400, detail="Aircraft with this registration already exists")

    _result = await session.execute(
        select(Aircraft).where(Aircraft.msn == aircraft_data["msn"])
    )

    msn_exist = _result.scalar_one_or_none()
    if msn_exist:
        raise HTTPException(status_code=400, detail="Aircraft with this msn already exists")

    
    aircraft = Aircraft(
        **aircraft_data
    )

    session.add(aircraft)
    await session.commit()
    await session.refresh(aircraft)
    return AircraftOut.from_orm(aircraft)