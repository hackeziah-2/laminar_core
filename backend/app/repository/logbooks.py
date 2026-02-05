import os
from typing import Optional, List, Tuple
from math import ceil

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.upload_path import UPLOAD_DIR
from app.models.logbooks import (
    EngineLogbook,
    AirframeLogbook,
    AvionicsLogbook,
    PropellerLogbook
)
from app.schemas.logbook_schema import (
    EngineLogbookCreate,
    EngineLogbookUpdate,
    EngineLogbookRead,
    AirframeLogbookCreate,
    AirframeLogbookUpdate,
    AirframeLogbookRead,
    AvionicsLogbookCreate,
    AvionicsLogbookUpdate,
    AvionicsLogbookRead,
    PropellerLogbookCreate,
    PropellerLogbookUpdate,
    PropellerLogbookRead,
)


# ========== Engine Logbook CRUD ==========
async def create_engine_logbook(
    session: AsyncSession,
    data: EngineLogbookCreate,
    upload_file: UploadFile = None
) -> EngineLogbookRead:
    """Create a new Engine Logbook entry."""
    logbook_data = data.dict()
    
    # Handle file upload (absolute path for write; store relative for DB/download)
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        logbook_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    entry = EngineLogbook(**logbook_data)
    try:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        await session.refresh(entry, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create engine logbook: {str(e)}")
    return EngineLogbookRead.from_orm(entry)


async def get_engine_logbook(
    session: AsyncSession,
    logbook_id: int
) -> Optional[EngineLogbookRead]:
    """Get an Engine Logbook entry by ID."""
    result = await session.execute(
        select(EngineLogbook)
        .options(selectinload(EngineLogbook.mechanic))
        .where(EngineLogbook.id == logbook_id)
        .where(EngineLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return EngineLogbookRead.from_orm(obj)


async def list_engine_logbooks(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[EngineLogbook], int]:
    """List Engine Logbook entries with pagination."""
    stmt = (
        select(EngineLogbook)
        .options(selectinload(EngineLogbook.mechanic))
        .where(EngineLogbook.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(EngineLogbook.aircraft_fk == aircraft_fk)

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                EngineLogbook.sequence_no.ilike(q),
                cast(EngineLogbook.description, String).ilike(q),
            )
        )

    sortable_fields = {
        "created_at": EngineLogbook.created_at,
        "updated_at": EngineLogbook.updated_at,
        "date": EngineLogbook.date,
        "sequence_no": EngineLogbook.sequence_no,
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
        stmt = stmt.order_by(EngineLogbook.date.desc(), EngineLogbook.sequence_no.asc())

    count_stmt = select(func.count()).select_from(EngineLogbook).where(EngineLogbook.is_deleted == False)
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(EngineLogbook.aircraft_fk == aircraft_fk)
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                EngineLogbook.sequence_no.ilike(q),
                cast(EngineLogbook.description, String).ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def update_engine_logbook(
    session: AsyncSession,
    logbook_id: int,
    logbook_in: EngineLogbookUpdate,
    upload_file: UploadFile = None
) -> Optional[EngineLogbookRead]:
    """Update an Engine Logbook entry."""
    result = await session.execute(
        select(EngineLogbook)
        .options(selectinload(EngineLogbook.mechanic))
        .where(EngineLogbook.id == logbook_id)
        .where(EngineLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = logbook_in.dict(exclude_unset=True)
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update engine logbook: {str(e)}")
    return EngineLogbookRead.from_orm(obj)


async def soft_delete_engine_logbook(
    session: AsyncSession,
    logbook_id: int
) -> bool:
    """Soft delete an Engine Logbook entry."""
    obj = await session.get(EngineLogbook, logbook_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


# ========== Airframe Logbook CRUD ==========
async def create_airframe_logbook(
    session: AsyncSession,
    data: AirframeLogbookCreate,
    upload_file: UploadFile = None
) -> AirframeLogbookRead:
    """Create a new Airframe Logbook entry."""
    logbook_data = data.dict()
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        logbook_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    entry = AirframeLogbook(**logbook_data)
    try:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        await session.refresh(entry, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create airframe logbook: {str(e)}")
    return AirframeLogbookRead.from_orm(entry)


async def get_airframe_logbook(
    session: AsyncSession,
    logbook_id: int
) -> Optional[AirframeLogbookRead]:
    """Get an Airframe Logbook entry by ID."""
    result = await session.execute(
        select(AirframeLogbook)
        .options(selectinload(AirframeLogbook.mechanic))
        .where(AirframeLogbook.id == logbook_id)
        .where(AirframeLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AirframeLogbookRead.from_orm(obj)


async def list_airframe_logbooks(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[AirframeLogbook], int]:
    """List Airframe Logbook entries with pagination."""
    stmt = (
        select(AirframeLogbook)
        .options(selectinload(AirframeLogbook.mechanic))
        .where(AirframeLogbook.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(AirframeLogbook.aircraft_fk == aircraft_fk)

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                AirframeLogbook.sequence_no.ilike(q),
                cast(AirframeLogbook.description, String).ilike(q),
            )
        )

    sortable_fields = {
        "created_at": AirframeLogbook.created_at,
        "updated_at": AirframeLogbook.updated_at,
        "date": AirframeLogbook.date,
        "sequence_no": AirframeLogbook.sequence_no,
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
        stmt = stmt.order_by(AirframeLogbook.date.desc(), AirframeLogbook.sequence_no.asc())

    count_stmt = select(func.count()).select_from(AirframeLogbook).where(AirframeLogbook.is_deleted == False)
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AirframeLogbook.aircraft_fk == aircraft_fk)
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                AirframeLogbook.sequence_no.ilike(q),
                cast(AirframeLogbook.description, String).ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def update_airframe_logbook(
    session: AsyncSession,
    logbook_id: int,
    logbook_in: AirframeLogbookUpdate,
    upload_file: UploadFile = None
) -> Optional[AirframeLogbookRead]:
    """Update an Airframe Logbook entry."""
    result = await session.execute(
        select(AirframeLogbook)
        .options(selectinload(AirframeLogbook.mechanic))
        .where(AirframeLogbook.id == logbook_id)
        .where(AirframeLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = logbook_in.dict(exclude_unset=True)
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update airframe logbook: {str(e)}")
    return AirframeLogbookRead.from_orm(obj)


async def soft_delete_airframe_logbook(
    session: AsyncSession,
    logbook_id: int
) -> bool:
    """Soft delete an Airframe Logbook entry."""
    obj = await session.get(AirframeLogbook, logbook_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


# ========== Avionics Logbook CRUD ==========
async def create_avionics_logbook(
    session: AsyncSession,
    data: AvionicsLogbookCreate,
    upload_file: UploadFile = None
) -> AvionicsLogbookRead:
    """Create a new Avionics Logbook entry."""
    logbook_data = data.dict()
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        logbook_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    entry = AvionicsLogbook(**logbook_data)
    try:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        await session.refresh(entry, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create avionics logbook: {str(e)}")
    return AvionicsLogbookRead.from_orm(entry)


async def get_avionics_logbook(
    session: AsyncSession,
    logbook_id: int
) -> Optional[AvionicsLogbookRead]:
    """Get an Avionics Logbook entry by ID."""
    result = await session.execute(
        select(AvionicsLogbook)
        .options(selectinload(AvionicsLogbook.mechanic))
        .where(AvionicsLogbook.id == logbook_id)
        .where(AvionicsLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AvionicsLogbookRead.from_orm(obj)


async def list_avionics_logbooks(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[AvionicsLogbook], int]:
    """List Avionics Logbook entries with pagination."""
    stmt = (
        select(AvionicsLogbook)
        .options(selectinload(AvionicsLogbook.mechanic))
        .where(AvionicsLogbook.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(AvionicsLogbook.aircraft_fk == aircraft_fk)

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                AvionicsLogbook.sequence_no.ilike(q),
                AvionicsLogbook.component.ilike(q),
                AvionicsLogbook.part_no.ilike(q),
                AvionicsLogbook.serial_no.ilike(q),
                cast(AvionicsLogbook.description, String).ilike(q),
            )
        )

    sortable_fields = {
        "created_at": AvionicsLogbook.created_at,
        "updated_at": AvionicsLogbook.updated_at,
        "date": AvionicsLogbook.date,
        "sequence_no": AvionicsLogbook.sequence_no,
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
        stmt = stmt.order_by(AvionicsLogbook.date.desc(), AvionicsLogbook.sequence_no.asc())

    count_stmt = select(func.count()).select_from(AvionicsLogbook).where(AvionicsLogbook.is_deleted == False)
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AvionicsLogbook.aircraft_fk == aircraft_fk)
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                AvionicsLogbook.sequence_no.ilike(q),
                AvionicsLogbook.component.ilike(q),
                AvionicsLogbook.part_no.ilike(q),
                AvionicsLogbook.serial_no.ilike(q),
                cast(AvionicsLogbook.description, String).ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def update_avionics_logbook(
    session: AsyncSession,
    logbook_id: int,
    logbook_in: AvionicsLogbookUpdate,
    upload_file: UploadFile = None
) -> Optional[AvionicsLogbookRead]:
    """Update an Avionics Logbook entry."""
    result = await session.execute(
        select(AvionicsLogbook)
        .options(selectinload(AvionicsLogbook.mechanic))
        .where(AvionicsLogbook.id == logbook_id)
        .where(AvionicsLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = logbook_in.dict(exclude_unset=True)
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update avionics logbook: {str(e)}")
    return AvionicsLogbookRead.from_orm(obj)


async def soft_delete_avionics_logbook(
    session: AsyncSession,
    logbook_id: int
) -> bool:
    """Soft delete an Avionics Logbook entry."""
    obj = await session.get(AvionicsLogbook, logbook_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


# ========== Propeller Logbook CRUD ==========
async def create_propeller_logbook(
    session: AsyncSession,
    data: PropellerLogbookCreate,
    upload_file: UploadFile = None
) -> PropellerLogbookRead:
    """Create a new Propeller Logbook entry."""
    logbook_data = data.dict()
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        logbook_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    entry = PropellerLogbook(**logbook_data)
    try:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        await session.refresh(entry, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create propeller logbook: {str(e)}")
    return PropellerLogbookRead.from_orm(entry)


async def get_propeller_logbook(
    session: AsyncSession,
    logbook_id: int
) -> Optional[PropellerLogbookRead]:
    """Get a Propeller Logbook entry by ID."""
    result = await session.execute(
        select(PropellerLogbook)
        .options(selectinload(PropellerLogbook.mechanic))
        .where(PropellerLogbook.id == logbook_id)
        .where(PropellerLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return PropellerLogbookRead.from_orm(obj)


async def list_propeller_logbooks(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[PropellerLogbook], int]:
    """List Propeller Logbook entries with pagination."""
    stmt = (
        select(PropellerLogbook)
        .options(selectinload(PropellerLogbook.mechanic))
        .where(PropellerLogbook.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(PropellerLogbook.aircraft_fk == aircraft_fk)

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                PropellerLogbook.sequence_no.ilike(q),
                cast(PropellerLogbook.description, String).ilike(q),
            )
        )

    sortable_fields = {
        "created_at": PropellerLogbook.created_at,
        "updated_at": PropellerLogbook.updated_at,
        "date": PropellerLogbook.date,
        "sequence_no": PropellerLogbook.sequence_no,
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
        stmt = stmt.order_by(PropellerLogbook.date.desc(), PropellerLogbook.sequence_no.asc())

    count_stmt = select(func.count()).select_from(PropellerLogbook).where(PropellerLogbook.is_deleted == False)
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(PropellerLogbook.aircraft_fk == aircraft_fk)
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                PropellerLogbook.sequence_no.ilike(q),
                cast(PropellerLogbook.description, String).ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def update_propeller_logbook(
    session: AsyncSession,
    logbook_id: int,
    logbook_in: PropellerLogbookUpdate,
    upload_file: UploadFile = None
) -> Optional[PropellerLogbookRead]:
    """Update a Propeller Logbook entry."""
    result = await session.execute(
        select(PropellerLogbook)
        .options(selectinload(PropellerLogbook.mechanic))
        .where(PropellerLogbook.id == logbook_id)
        .where(PropellerLogbook.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = logbook_in.dict(exclude_unset=True)
    
    # Handle file upload
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["upload_file"] = f"uploads/{upload_file.filename}"
    
    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ['mechanic'])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update propeller logbook: {str(e)}")
    return PropellerLogbookRead.from_orm(obj)


async def soft_delete_propeller_logbook(
    session: AsyncSession,
    logbook_id: int
) -> bool:
    """Soft delete a Propeller Logbook entry."""
    obj = await session.get(PropellerLogbook, logbook_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
