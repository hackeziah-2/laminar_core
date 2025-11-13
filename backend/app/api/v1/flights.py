from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app import schemas
from app.repository.flight_crud import create_flight, get_flight, update_flight, delete_flight, list_flights
from app.database import get_session
from math import ceil

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])

@router.post("/", response_model=schemas.flight_schema.FlightOut)
async def api_create_flight(flight_in: schemas.flight_schema.FlightCreate, session: AsyncSession = Depends(get_session)):
    return await create_flight(session, flight_in)

@router.get("/", response_model=List[schemas.flight_schema.FlightOut])
async def api_list_flights(limit: int = Query(10, ge=1, le=100), page: int = Query(1, ge=1), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    offset = (page - 1) * limit
    items, total = await list_flights(session, limit=limit, offset=offset, search=search)
    return items

@router.get("/paged")
async def api_list_paged(limit: int = Query(10, ge=1, le=100), page: int = Query(1, ge=1), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    offset = (page - 1) * limit
    items, total = await list_flights(session, limit=limit, offset=offset, search=search)
    pages = ceil(total / limit) if total else 0
    return {"items": items, "total": total, "page": page, "pages": pages}

@router.get("/{flight_id}", response_model=schemas.flight_schema.FlightOut)
async def api_get(flight_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_flight(session, flight_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Flight not found")
    return obj

@router.put("/{flight_id}", response_model=schemas.flight_schema.FlightOut)
async def api_update(flight_id: int, flight_in: schemas.flight_schema.FlightUpdate, session: AsyncSession = Depends(get_session)):
    obj = await update_flight(session, flight_id, flight_in)
    if not obj:
        raise HTTPException(status_code=404, detail="Flight not found")
    return obj
    
@router.delete("/{flight_id}")
async def api_delete(flight_id: int, session: AsyncSession = Depends(get_session)):
    deleted = await delete_flight(session, flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Flight not found")
    return {"ok": True}
