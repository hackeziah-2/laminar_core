from math import ceil
from typing import List, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_technical_log_schema
from app.repository.aircraft_technical_log import (
    list_aircraft_technical_logs,
    get_aircraft_technical_log,
    create_aircraft_technical_log,
    update_aircraft_technical_log,
    soft_delete_aircraft_technical_log
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/aircraft-technical-log",
    tags=["aircraft-technical-log"]
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    sort: Optional[str] = Query(
        "",
        description="Example: -created_at,sequence_no"
    ),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Aircraft Technical Log entries."""
    offset = (page - 1) * limit
    items, total = await list_aircraft_technical_logs(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        aircraft_fk=aircraft_fk,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/{log_id}",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead
)
async def api_get(
    log_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Aircraft Technical Log entry by ID."""
    obj = await get_aircraft_technical_log(session, log_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Aircraft Technical Log not found"
        )
    return obj


@router.post(
    "/",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: aircraft_technical_log_schema.AircraftTechnicalLogCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new Aircraft Technical Log entry."""
    return await create_aircraft_technical_log(session, payload)


@router.put(
    "/{log_id}",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead
)
async def api_update(
    log_id: int,
    log_in: aircraft_technical_log_schema.AircraftTechnicalLogUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an Aircraft Technical Log entry."""
    updated = await update_aircraft_technical_log(
        session=session,
        log_id=log_id,
        log_in=log_in,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Aircraft Technical Log not found"
        )

    return updated


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def api_delete(
    log_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Aircraft Technical Log entry."""
    deleted = await soft_delete_aircraft_technical_log(session, log_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aircraft Technical Log not found",
        )
    return {"ok": True}
