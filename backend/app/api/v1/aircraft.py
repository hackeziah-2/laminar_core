import json

from math import ceil
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_schema
from app.repository.aircraft import (
    list_aircraft,
    get_aircraft, update_aircraft, 
    create_aircraft_with_file
)
from app.database import get_session

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircrafts"])


@router.get("/", response_model=List[aircraft_schema.AircraftOut])
async def api_list_aircraft(limit: int = Query(10, ge=1, le=100), page: int = Query(1, ge=1), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    pass


@router.put("/{aircraft_id}", response_model=aircraft_schema.AircraftUpdate)
async def api_update(aircraft_id: int, aircraft_in: aircraft_schema.AircraftUpdate, session: AsyncSession = Depends(get_session)):
    obj = await update_aircraft(session, aircraft_id, aircraft_in)
    if not obj:
        raise HTTPException(status_code=404, detail="Flight not found")
    return obj

@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100), 
    page: int = Query(1, ge=1), 
    search: Optional[str] = None, 
    status: aircraft_schema.AircrarftStatus | None = Query(
        None, description="Filter by status", enum=["active", "inactive", "maintenance"]),
    session: AsyncSession = Depends(get_session)
):
    offset = (page - 1) * limit
    items, total = await list_aircraft(session, limit=limit, offset=offset, search=search, status=status)
    pages = ceil(total / limit) if total else 0
    return {"items": items, "total": total, "page": page, "pages": pages}

@router.get("/{aircraft_id}", response_model=aircraft_schema.AircraftOut)
async def api_get(aircraft_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_aircraft(session, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return obj

@router.post("/", response_model=aircraft_schema.AircraftOut)
async def api_create_aircraft_with_file(
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):  
    
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftCreate(**parsed)

    return await create_aircraft_with_file(
        session=session,
        data=aircraft_data,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file
    )