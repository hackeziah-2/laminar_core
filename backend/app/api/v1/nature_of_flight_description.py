from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.api.pagination import Pagination, paged_payload, pagination_params
from app.constants.audit import (
    NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
    NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
)
from app.database import get_session
from app.models.account import AccountInformation
from app.models.aircraft_techinical_log import TypeEnum
from app.repository.aircraft import get_aircraft
from app.repository.nature_of_flight_description import (
    create_nature_of_flight_description,
    get_nature_of_flight_description,
    get_nature_of_flight_description_by_aircraft,
    get_nature_of_flight_description_by_aircraft_and_nature,
    list_nature_of_flight_descriptions,
    soft_delete_nature_of_flight_description,
    soft_delete_nature_of_flight_description_by_aircraft,
    update_nature_of_flight_description,
)
from app.schemas.nature_of_flight_description_schema import (
    NatureOfFlightDescriptionAircraftCreate,
    NatureOfFlightDescriptionCreate,
    NatureOfFlightDescriptionLookupRead,
    NatureOfFlightDescriptionRead,
    NatureOfFlightDescriptionUpdate,
)

router = APIRouter(
    prefix="/api/v1/nature-of-flight-descriptions",
    tags=["nature-of-flight-descriptions"],
)

router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["nature-of-flight-descriptions"],
)


@router.get("/paged")
async def api_list_paged(
    pagination: Pagination = Depends(pagination_params),
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    nature_of_flight: Optional[TypeEnum] = Query(
        None, description="Filter by nature of flight (e.g. TR, PSF, ATL_REPL)"
    ),
    search: Optional[str] = Query(
        None,
        description="Search remarks, action_taken, nature_of_flight, or aircraft registration",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort fields (comma-separated). Prefix '-' for descending. Example: -created_at,nature_of_flight",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of Nature of Flight Description entries."""
    items, total = await list_nature_of_flight_descriptions(
        session=session,
        limit=pagination.limit,
        offset=pagination.offset,
        search=search.strip() if search and search.strip() else None,
        sort=sort or "",
        aircraft_fk=aircraft_fk,
        nature_of_flight=nature_of_flight.value if nature_of_flight else None,
    )
    return paged_payload(
        [NatureOfFlightDescriptionRead.from_orm(i) for i in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{entry_id}", response_model=NatureOfFlightDescriptionRead)
async def api_get(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a Nature of Flight Description by ID."""
    obj = await get_nature_of_flight_description(session, entry_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return NatureOfFlightDescriptionRead.from_orm(obj)


@router.post(
    "/",
    response_model=NatureOfFlightDescriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    request: Request,
    payload: NatureOfFlightDescriptionCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a Nature of Flight Description entry."""
    aircraft = await get_aircraft(session, payload.aircraft_fk)
    if not aircraft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aircraft not found",
        )
    return await create_nature_of_flight_description(
        session,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )


@router.put("/{entry_id}", response_model=NatureOfFlightDescriptionRead)
async def api_update(
    entry_id: int,
    request: Request,
    payload: NatureOfFlightDescriptionUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update a Nature of Flight Description entry."""
    if payload.aircraft_fk is not None:
        aircraft = await get_aircraft(session, payload.aircraft_fk)
        if not aircraft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aircraft not found",
            )
    updated = await update_nature_of_flight_description(
        session,
        entry_id,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return updated


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    entry_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Soft delete a Nature of Flight Description entry."""
    deleted = await soft_delete_nature_of_flight_description(
        session,
        entry_id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return None


@router_aircraft_scoped.get("/{aircraft_id}/nature-of-flight-descriptions/paged")
async def api_list_by_aircraft_paged(
    aircraft_id: int,
    pagination: Pagination = Depends(pagination_params),
    nature_of_flight: Optional[TypeEnum] = Query(
        None, description="Filter by nature of flight (e.g. TR, PSF, ATL_REPL)"
    ),
    search: Optional[str] = Query(
        None,
        description="Search remarks, action_taken, or nature_of_flight",
    ),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of Nature of Flight Description entries for an aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aircraft not found")
    items, total = await list_nature_of_flight_descriptions(
        session=session,
        limit=pagination.limit,
        offset=pagination.offset,
        search=search.strip() if search and search.strip() else None,
        sort=sort or "",
        aircraft_fk=aircraft_id,
        nature_of_flight=nature_of_flight.value if nature_of_flight else None,
    )
    return paged_payload(
        [NatureOfFlightDescriptionRead.from_orm(i) for i in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router_aircraft_scoped.get(
    "/{aircraft_id}/nature-of-flight-descriptions/{nature_of_flight}",
    response_model=NatureOfFlightDescriptionLookupRead,
)
async def api_get_by_aircraft_and_nature(
    aircraft_id: int,
    nature_of_flight: TypeEnum,
    session: AsyncSession = Depends(get_session),
):
    """Get remarks and action_taken for an aircraft and nature of flight."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aircraft not found")
    obj = await get_nature_of_flight_description_by_aircraft_and_nature(
        session, aircraft_id, nature_of_flight
    )
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return NatureOfFlightDescriptionLookupRead.from_orm(obj)


@router_aircraft_scoped.post(
    "/{aircraft_id}/nature-of-flight-descriptions/",
    response_model=NatureOfFlightDescriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_by_aircraft(
    aircraft_id: int,
    request: Request,
    payload: NatureOfFlightDescriptionAircraftCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a Nature of Flight Description for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aircraft not found")
    create_payload = NatureOfFlightDescriptionCreate(
        aircraft_fk=aircraft_id,
        nature_of_flight=payload.nature_of_flight,
        remarks=payload.remarks,
        action_taken=payload.action_taken,
    )
    return await create_nature_of_flight_description(
        session,
        create_payload,
        audit_account_id=current_account.id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )


@router_aircraft_scoped.put(
    "/{aircraft_id}/nature-of-flight-descriptions/{entry_id}",
    response_model=NatureOfFlightDescriptionRead,
)
async def api_update_by_aircraft(
    aircraft_id: int,
    entry_id: int,
    request: Request,
    payload: NatureOfFlightDescriptionUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update a Nature of Flight Description scoped to aircraft."""
    existing = await get_nature_of_flight_description_by_aircraft(
        session, entry_id, aircraft_id
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    updated = await update_nature_of_flight_description(
        session,
        entry_id,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return updated


@router_aircraft_scoped.delete(
    "/{aircraft_id}/nature-of-flight-descriptions/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def api_delete_by_aircraft(
    aircraft_id: int,
    entry_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Soft delete a Nature of Flight Description scoped to aircraft."""
    deleted = await soft_delete_nature_of_flight_description_by_aircraft(
        session,
        entry_id,
        aircraft_id,
        audit_module_name=NATURE_OF_FLIGHT_DESCRIPTION_MODULE_NAME,
        audit_table_name=NATURE_OF_FLIGHT_DESCRIPTION_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nature of Flight Description not found",
        )
    return None
