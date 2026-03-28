from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.models.aircraft_statutory_certificate import CategoryTypeEnum
from app.repository.aircraft_statutory_certificate_history import (
    list_aircraft_statutory_certificates_history,
    get_aircraft_statutory_certificate_history,
    create_aircraft_statutory_certificate_history,
)
from app.schemas.aircraft_statutory_certificate_history_schema import (
    AircraftStatutoryCertificateHistoryCreate,
    AircraftStatutoryCertificateHistoryRead,
)

router = APIRouter(
    prefix="/api/v1/aircraft-statutory-certificates-history",
    tags=["aircraft-statutory-certificates-history"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    aircraft_fk: Optional[int] = Query(None),
    asc_history: Optional[int] = Query(None),
    category_type: Optional[CategoryTypeEnum] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_aircraft_statutory_certificates_history(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_fk,
        asc_history=asc_history,
        category_type=category_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AircraftStatutoryCertificateHistoryRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{asc_history}/paged")
async def api_list_paged_by_asc_history(
    asc_history: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    category_type: Optional[CategoryTypeEnum] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_aircraft_statutory_certificates_history(
        session=session,
        limit=limit,
        offset=offset,
        asc_history=asc_history,
        category_type=category_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AircraftStatutoryCertificateHistoryRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{history_id}", response_model=AircraftStatutoryCertificateHistoryRead)
async def api_get(
    history_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_aircraft_statutory_certificate_history(session, history_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History record not found")
    return AircraftStatutoryCertificateHistoryRead.from_orm(obj)


@router.post(
    "/",
    response_model=AircraftStatutoryCertificateHistoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    body: AircraftStatutoryCertificateHistoryCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    return await create_aircraft_statutory_certificate_history(
        session, body, audit_account_id=current_account.id
    )
