import os

from sqlalchemy import select, or_, cast, String
from sqlalchemy.sql import func
from fastapi import Query, Depends, UploadFile, File, Form, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

ensure_uploads_dir()

from app.models.aircraft import Aircraft
from app.models.aircraft_logbook_entries import AircraftLogbookEntry
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_monitoring import LDNDMonitoring
from app.models.ad_monitoring import ADMonitoring, WorkOrderADMonitoring
from app.models.logbooks import (
    EngineLogbook,
    AirframeLogbook,
    AvionicsLogbook,
    PropellerLogbook,
)
from app.models.tcc_maintenance import TCCMaintenance
from app.models.document_on_board import DocumentOnBoard
from app.models.cpcp_monitoring import CPCPMonitoring
from app.schemas.aircraft_schema import AircraftCreate, AircraftOut, AircraftUpdate
from typing import List, Optional, Tuple

async def get_aircraft(session: AsyncSession, id: int) -> Optional[AircraftOut]:
    aircraft = await get_aircraft_raw(session, id)
    if not aircraft:
        return None
    return AircraftOut.from_orm(aircraft)


async def get_aircraft_raw(session: AsyncSession, id: int):
    """Return the Aircraft ORM model or None (for internal use, e.g. file paths)."""
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    return result.scalar_one_or_none()

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
    """Soft delete aircraft and all connected data (cascade).
    Sets is_deleted=True on aircraft and all related records in a single transaction.
    """
    result = await session.execute(
        select(Aircraft).where(Aircraft.id == id).where(Aircraft.is_deleted == False)
    )
    aircraft = result.scalar_one_or_none()
    if not aircraft:
        return False

    aircraft_id = aircraft.id

    async def _soft_delete_many(model, fk_col, fk_val):
        """Helper: soft delete all non-deleted records for given FK."""
        stmt = select(model).where(fk_col == fk_val).where(model.is_deleted == False)
        r = await session.execute(stmt)
        for obj in r.scalars().all():
            obj.soft_delete()
            session.add(obj)

    # WorkOrderADMonitoring: soft delete work orders for ADs belonging to this aircraft
    ad_stmt = select(ADMonitoring.id).where(
        ADMonitoring.aircraft_fk == aircraft_id
    ).where(ADMonitoring.is_deleted == False)
    ad_ids = [row[0] for row in (await session.execute(ad_stmt)).all()]
    if ad_ids:
        wo_stmt = select(WorkOrderADMonitoring).where(
            WorkOrderADMonitoring.ad_monitoring_fk.in_(ad_ids),
            WorkOrderADMonitoring.is_deleted == False,
        )
        for wo in (await session.execute(wo_stmt)).scalars().all():
            wo.soft_delete()
            session.add(wo)

    # ADMonitoring
    await _soft_delete_many(ADMonitoring, ADMonitoring.aircraft_fk, aircraft_id)
    # LDNDMonitoring
    await _soft_delete_many(LDNDMonitoring, LDNDMonitoring.aircraft_fk, aircraft_id)
    # AircraftTechnicalLog
    await _soft_delete_many(AircraftTechnicalLog, AircraftTechnicalLog.aircraft_fk, aircraft_id)
    # AircraftLogbookEntry
    await _soft_delete_many(AircraftLogbookEntry, AircraftLogbookEntry.aircraft_id, aircraft_id)
    # EngineLogbook, AirframeLogbook, AvionicsLogbook, PropellerLogbook
    await _soft_delete_many(EngineLogbook, EngineLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(AirframeLogbook, AirframeLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(AvionicsLogbook, AvionicsLogbook.aircraft_fk, aircraft_id)
    await _soft_delete_many(PropellerLogbook, PropellerLogbook.aircraft_fk, aircraft_id)
    # TCCMaintenance
    await _soft_delete_many(TCCMaintenance, TCCMaintenance.aircraft_fk, aircraft_id)
    # DocumentOnBoard
    await _soft_delete_many(DocumentOnBoard, DocumentOnBoard.aircraft_id, aircraft_id)
    # CPCPMonitoring
    await _soft_delete_many(CPCPMonitoring, CPCPMonitoring.aircraft_id, aircraft_id)

    # Aircraft
    aircraft.soft_delete()
    session.add(aircraft)
    await session.commit()
    return True
