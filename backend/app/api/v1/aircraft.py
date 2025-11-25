from math import ceil

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_schema
from app.repository.aircraft import create_aircraft, list_aircraft, get_aircraft
from app.database import get_session

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircrafts"])

@router.post("/", response_model=aircraft_schema.AircraftOut)
async def api_create_aircraft(aircraft_data: aircraft_schema.AircraftCreate, session: AsyncSession = Depends(get_session)):
    return await create_aircraft(session, aircraft_data)


@router.get("/", response_model=List[aircraft_schema.AircraftOut])
async def api_list_aircraft(limit: int = Query(10, ge=1, le=100), page: int = Query(1, ge=1), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    pass
    # offset = (page - 1) * limit
    # items, total = await list_aircraft(session, limit=limit, offset=offset, search=search)
    # return items


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
