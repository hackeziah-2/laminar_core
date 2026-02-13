from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import tcc_maintenance_schema
from app.repository.tcc_maintenance import (
    create_tcc_maintenance,
    get_tcc_maintenance,
    get_tcc_maintenance_by_aircraft,
    list_tcc_maintenances,
    update_tcc_maintenance,
    soft_delete_tcc_maintenance,
    soft_delete_tcc_maintenance_by_aircraft,
)
from app.repository.aircraft import get_aircraft
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/tcc-maintenance",
    tags=["tcc-maintenance"],
)

# Aircraft-scoped router: /api/v1/aircraft/{aircraft_id}/tcc-maintenance/...
router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["tcc-maintenance"],
)


@router.get("/paged")
async def api_list_tcc_maintenances_paged(
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search in part_number, serial_number, description"),
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    atl_ref: Optional[int] = Query(None, description="Filter by ATL (aircraft_technical_log) ID"),
    category: Optional[str] = Query(None, description="Filter by category: Powerplant, Airframe, Inspection Servicing"),
    sort: Optional[str] = Query(
        "",
        description="Sort fields (comma-separated). Prefix with '-' for descending. Example: -created_at,part_number",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of TCC Maintenance entries."""
    offset = (page - 1) * limit
    items, total = await list_tcc_maintenances(
        session=session,
        limit=limit,
        offset=offset,
        search=search.strip() if search and search.strip() else None,
        aircraft_fk=aircraft_fk,
        atl_ref=atl_ref,
        category=category,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [
        tcc_maintenance_schema.TCCMaintenanceRead.from_orm(item)
        for item in items
    ]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/{maintenance_id}",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    summary="Get TCC Maintenance by ID (edit entry)",
    description="Retrieve a single TCC Maintenance entry by ID. For ATL Reference in edit form: GET /api/v1/aircraft-technical-log/search?search={sequence_no} (optional &aircraft_id={id}); use response item id as atl_ref.",
)
async def api_get_tcc_maintenance(
    maintenance_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single TCC Maintenance entry by ID."""
    obj = await get_tcc_maintenance(session, maintenance_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="TCC Maintenance not found",
        )
    return obj


@router.post(
    "/",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create TCC Maintenance entry",
    description="Create a new TCC Maintenance entry. Required: aircraft_fk, part_number. Optional: atl_ref.",
)
async def api_create_tcc_maintenance(
    payload: tcc_maintenance_schema.TCCMaintenanceCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new TCC Maintenance entry."""
    return await create_tcc_maintenance(session, payload)


@router.put(
    "/{maintenance_id}",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    summary="Update TCC Maintenance entry",
    description="Update an existing TCC Maintenance entry. Only provided fields are updated. Returns 404 if not found.",
)
async def api_update_tcc_maintenance(
    maintenance_id: int,
    payload: tcc_maintenance_schema.TCCMaintenanceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a TCC Maintenance entry."""
    updated = await update_tcc_maintenance(session, maintenance_id, payload)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="TCC Maintenance not found",
        )
    return updated


@router.delete(
    "/{maintenance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete TCC Maintenance entry",
    description="Soft delete a TCC Maintenance entry (sets is_deleted). Returns 404 if not found.",
)
async def api_delete_tcc_maintenance(
    maintenance_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a TCC Maintenance entry."""
    deleted = await soft_delete_tcc_maintenance(session, maintenance_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TCC Maintenance not found",
        )
    return None


# ========== Aircraft-scoped endpoints: /api/v1/aircraft/{aircraft_id}/tcc-maintenance/... ==========

@router_aircraft_scoped.get(
    "/{aircraft_id}/tcc-maintenance/paged",
    summary="List TCC Maintenance for aircraft (paginated)",
    description="Get paginated list of TCC Maintenance entries for a specific aircraft. aircraft_id is required.",
)
async def api_list_tcc_maintenances_by_aircraft_paged(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    atl_ref: Optional[int] = Query(None),
    category: Optional[str] = Query(None, description="Filter by category: Powerplant, Airframe, Inspection Servicing"),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of TCC Maintenance entries for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    items, total = await list_tcc_maintenances(
        session=session,
        limit=limit,
        offset=offset,
        search=search.strip() if search and search.strip() else None,
        aircraft_fk=aircraft_id,
        atl_ref=atl_ref,
        category=category,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [
        tcc_maintenance_schema.TCCMaintenanceRead.from_orm(item)
        for item in items
    ]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.get(
    "/{aircraft_id}/tcc-maintenance/{maintenance_id}",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    summary="Get TCC Maintenance by ID for aircraft (edit entry)",
    description="Returns TCC entry for editing. ATL Reference: search via GET /api/v1/aircraft-technical-log/search?search={sequence_no}&aircraft_id={aircraft_id}; use response item id as atl_ref.",
)
async def api_get_tcc_maintenance_by_aircraft(
    aircraft_id: int,
    maintenance_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single TCC Maintenance entry by ID for a specific aircraft (e.g. for edit form)."""
    obj = await get_tcc_maintenance_by_aircraft(session, maintenance_id, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="TCC Maintenance not found")
    return obj


@router_aircraft_scoped.post(
    "/{aircraft_id}/tcc-maintenance/",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create TCC Maintenance for aircraft",
    description="Create a new TCC Maintenance entry for the given aircraft. aircraft_id from path is required; part_number required in body. atl_ref optional.",
)
async def api_create_tcc_maintenance_by_aircraft(
    aircraft_id: int,
    payload: tcc_maintenance_schema.TCCMaintenanceCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new TCC Maintenance entry for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    # Override aircraft_fk with path aircraft_id (required)
    data = payload.dict()
    data["aircraft_fk"] = aircraft_id
    create_payload = tcc_maintenance_schema.TCCMaintenanceCreate(**data)
    return await create_tcc_maintenance(session, create_payload)


@router_aircraft_scoped.put(
    "/{aircraft_id}/tcc-maintenance/{maintenance_id}",
    response_model=tcc_maintenance_schema.TCCMaintenanceRead,
    summary="Update TCC Maintenance for aircraft (edit entry)",
    description="Update TCC entry. atl_ref: set from ATL search GET /api/v1/aircraft-technical-log/search?search={sequence_no}&aircraft_id={aircraft_id}; use response item id.",
)
async def api_update_tcc_maintenance_by_aircraft(
    aircraft_id: int,
    maintenance_id: int,
    payload: tcc_maintenance_schema.TCCMaintenanceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a TCC Maintenance entry for a specific aircraft. ATL Reference: use /api/v1/aircraft-technical-log/search?search={sequence_no} and set atl_ref to the chosen item id."""
    existing = await get_tcc_maintenance_by_aircraft(session, maintenance_id, aircraft_id)
    if not existing:
        raise HTTPException(status_code=404, detail="TCC Maintenance not found")
    updated = await update_tcc_maintenance(session, maintenance_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="TCC Maintenance not found")
    return updated


@router_aircraft_scoped.delete(
    "/{aircraft_id}/tcc-maintenance/{maintenance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete TCC Maintenance for aircraft",
)
async def api_delete_tcc_maintenance_by_aircraft(
    aircraft_id: int,
    maintenance_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a TCC Maintenance entry for a specific aircraft."""
    deleted = await soft_delete_tcc_maintenance_by_aircraft(
        session, maintenance_id, aircraft_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TCC Maintenance not found",
        )
    return None
