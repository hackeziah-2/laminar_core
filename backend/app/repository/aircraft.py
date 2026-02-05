import os

from sqlalchemy import select, or_, cast, String
from sqlalchemy.sql import func
from fastapi import Query, Depends, UploadFile, File, Form, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

ensure_uploads_dir()

from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftCreate, AircraftOut, AircraftUpdate
from typing import List, Optional, Tuple

async def get_aircraft(session: AsyncSession, id: int) -> Optional[AircraftOut]:
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    aircraft = result.scalar_one_or_none()
    if not aircraft:
        return None
    return AircraftOut.from_orm(aircraft)

async def list_aircraft(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    status: Optional[str] = "all",
    sort: Optional[str] = "",
):
    stmt = select(Aircraft).where(Aircraft.is_deleted == False)

    # Search
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                Aircraft.registration.ilike(q),
                Aircraft.base.ilike(q),
                Aircraft.model.ilike(q),
            )
        )

    # Status filter
    if status and status.lower() != "all":
        stmt = stmt.where(
            func.lower(cast(Aircraft.status, String)) == status.lower()
        )

    # Whitelist sortable fields (IMPORTANT)
    sortable_fields = {
        "registration": Aircraft.registration,
        "base": Aircraft.base,
        "model": Aircraft.model,
        "status": Aircraft.status,
        "created_at": Aircraft.created_at,
        "updated_at": Aircraft.updated_at,
    }
    
    # Multi-sort logic
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")

            column = sortable_fields.get(field_name)
            if column is None:
                continue  # ignore invalid fields safely

            stmt = stmt.order_by(
                column.desc() if desc_order else column.asc()
            )
    else:
        stmt = stmt.order_by(Aircraft.created_at.desc())

    # Total count (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(Aircraft)
        .where(Aircraft.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                Aircraft.registration.ilike(q),
                Aircraft.base.ilike(q),
                Aircraft.model.ilike(q),
            )
        )

    if status and status.lower() != "all":
        count_stmt = count_stmt.where(
            func.lower(cast(Aircraft.status, String)) == status.lower()
        )

    total_count = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

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
        engine_path = os.path.join(str(UPLOAD_DIR), engine_file.filename)
        with open(engine_path, "wb") as f:
            f.write(await engine_file.read())

    propeller_path = None
    if propeller_file:
        propeller_path = os.path.join(str(UPLOAD_DIR), propeller_file.filename)
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

async def update_aircraft_with_file(
    session: AsyncSession,
    aircraft_id: int,
    data: AircraftUpdate,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
):
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == aircraft_id)
    )
    aircraft = result.scalar_one_or_none()

    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    update_data = data.dict(exclude_unset=True)

    # --- Handle engine file ---
    if engine_file:
        engine_path = os.path.join(str(UPLOAD_DIR), engine_file.filename)
        with open(engine_path, "wb") as f:
            f.write(await engine_file.read())
        update_data["engine_arc"] = engine_path

    # --- Handle propeller file ---
    if propeller_file:
        propeller_path = os.path.join(str(UPLOAD_DIR), propeller_file.filename)
        with open(propeller_path, "wb") as f:
            f.write(await propeller_file.read())
        update_data["propeller_arc"] = propeller_path

    # --- Uniqueness checks (exclude current aircraft) ---
    if "registration" in update_data:
        result = await session.execute(
            select(Aircraft).where(
                Aircraft.registration == update_data["registration"],
                Aircraft.id != aircraft_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Registration already exists")

    if "msn" in update_data:
        result = await session.execute(
            select(Aircraft).where(
                Aircraft.msn == update_data["msn"],
                Aircraft.id != aircraft_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="MSN already exists")

    # --- Apply updates ---
    for key, value in update_data.items():
        setattr(aircraft, key, value)
    print("newsss")
    await session.commit()
    await session.refresh(aircraft)

    return AircraftOut.from_orm(aircraft)

async def soft_delete_aircraft(
    session: AsyncSession, id: int
) -> bool:
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    aircraft = result.scalar_one_or_none()
    if not aircraft:
        return False

    aircraft.soft_delete()
    session.add(aircraft)
    await session.commit()
    return True
