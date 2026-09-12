from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app import schemas
from app.repository.flight_crud import create_flight, get_flight, update_flight, delete_flight, list_flights
from app.api.deps import get_current_active_account
from app.api.pagination import Pagination, paged_payload, pagination_params
from app.database import get_session
from app.models.account import AccountInformation

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])

@router.post("/", response_model=schemas.flight_schema.FlightOut)
async def api_create_flight(
    flight_in: schemas.flight_schema.FlightCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    return await create_flight(
        session, flight_in, audit_account_id=current_account.id
    )

@router.get("/", response_model=List[schemas.flight_schema.FlightOut])
async def api_list_flights(pagination: Pagination = Depends(pagination_params), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    items, total = await list_flights(session, limit=pagination.limit, offset=pagination.offset, search=search)
    return items

@router.get("/paged")
async def api_list_paged(pagination: Pagination = Depends(pagination_params), search: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    items, total = await list_flights(session, limit=pagination.limit, offset=pagination.offset, search=search)
    return paged_payload(items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/{flight_id}", response_model=schemas.flight_schema.FlightOut)
async def api_get(flight_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_flight(session, flight_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Flight not found")
    return obj

@router.put("/{flight_id}", response_model=schemas.flight_schema.FlightOut)
async def api_update(
    flight_id: int,
    flight_in: schemas.flight_schema.FlightUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    obj = await update_flight(
        session,
        flight_id,
        flight_in,
        audit_account_id=current_account.id,
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Flight not found")
    return obj
    
@router.delete("/{flight_id}")
async def api_delete(flight_id: int, session: AsyncSession = Depends(get_session)):
    deleted = await delete_flight(session, flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Flight not found")
    return {"ok": True}
