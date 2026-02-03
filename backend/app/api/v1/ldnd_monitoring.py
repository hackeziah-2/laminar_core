from math import ceil
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ldnd_monitoring_schema
from app.repository.ldnd_monitoring import (
    get_ldnd_monitoring,
    get_ldnd_monitoring_by_aircraft,
    get_ldnd_latest_by_aircraft,
    list_ldnd_monitoring,
    create_ldnd_monitoring,
    update_ldnd_monitoring,
    soft_delete_ldnd_monitoring,
    soft_delete_ldnd_monitoring_by_aircraft,
)
from app.repository.aircraft import get_aircraft
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/ldnd-monitoring",
    tags=["ldnd-monitoring"],
)

# Aircraft-scoped router: /api/v1/aircraft/{aircraft_id}/ldnd-monitoring/...
router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["ldnd-monitoring"],
)


@router.get("/paged")
async def api_list_ldnd_monitoring_paged(
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    inspection_type: Optional[str] = Query(None, description="Filter by inspection type (partial match)"),
    sort: Optional[str] = Query("", description="Sort fields (comma-separated). Prefix '-' for descending."),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of LDNDMonitoring entries."""
    offset = (page - 1) * limit
    items, total = await list_ldnd_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_fk,
        inspection_type=inspection_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [ldnd_monitoring_schema.LDNDMonitoringRead.from_orm(item) for item in items]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/{ldnd_id}",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    summary="Get LDNDMonitoring by ID",
)
async def api_get_ldnd_monitoring(
    ldnd_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single LDNDMonitoring entry by ID."""
    obj = await get_ldnd_monitoring(session, ldnd_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return obj


@router.post(
    "/",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create LDNDMonitoring entry",
)
async def api_create_ldnd_monitoring(
    data: ldnd_monitoring_schema.LDNDMonitoringCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new LDNDMonitoring entry."""
    return await create_ldnd_monitoring(session, data)


@router.put(
    "/{ldnd_id}",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    summary="Update LDNDMonitoring entry",
)
async def api_update_ldnd_monitoring(
    ldnd_id: int,
    data: ldnd_monitoring_schema.LDNDMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an LDNDMonitoring entry."""
    updated = await update_ldnd_monitoring(session, ldnd_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return updated


@router.delete(
    "/{ldnd_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete LDNDMonitoring entry",
)
async def api_delete_ldnd_monitoring(
    ldnd_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an LDNDMonitoring entry (sets is_deleted)."""
    deleted = await soft_delete_ldnd_monitoring(session, ldnd_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return None


# ========== Aircraft-scoped endpoints ==========

@router_aircraft_scoped.get(
    "/{aircraft_id}/ldnd-monitoring/latest",
    response_model=ldnd_monitoring_schema.LDNDLatestResponse,
    summary="Get latest maintenance summary (current tach, next inspection, last updated)",
)
async def api_get_ldnd_latest_by_aircraft(
    aircraft_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get current tach, next inspection, and last updated from LDND monitoring for this aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return await get_ldnd_latest_by_aircraft(session, aircraft_id)


@router_aircraft_scoped.get(
    "/{aircraft_id}/ldnd-monitoring/paged",
    summary="List LDND monitoring for aircraft (paginated)",
)
async def api_list_ldnd_monitoring_by_aircraft_paged(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    inspection_type: Optional[str] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of LDNDMonitoring entries for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    items, total = await list_ldnd_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_id,
        inspection_type=inspection_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [ldnd_monitoring_schema.LDNDMonitoringRead.from_orm(item) for item in items]
    return {"items": items_schemas, "total": total, "page": page, "pages": pages}


@router_aircraft_scoped.get(
    "/{aircraft_id}/ldnd-monitoring/{ldnd_id}",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    summary="Get LDND monitoring by ID for aircraft",
)
async def api_get_ldnd_monitoring_by_aircraft(
    aircraft_id: int,
    ldnd_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single LDNDMonitoring entry by ID for a specific aircraft."""
    obj = await get_ldnd_monitoring_by_aircraft(session, ldnd_id, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return obj


@router_aircraft_scoped.post(
    "/{aircraft_id}/ldnd-monitoring/",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create LDND monitoring for aircraft",
)
async def api_create_ldnd_monitoring_by_aircraft(
    aircraft_id: int,
    data: ldnd_monitoring_schema.LDNDMonitoringCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new LDNDMonitoring entry for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    create_data = ldnd_monitoring_schema.LDNDMonitoringCreate(
        **{**data.dict(), "aircraft_fk": aircraft_id}
    )
    return await create_ldnd_monitoring(session, create_data)


@router_aircraft_scoped.put(
    "/{aircraft_id}/ldnd-monitoring/{ldnd_id}",
    response_model=ldnd_monitoring_schema.LDNDMonitoringRead,
    summary="Update LDND monitoring for aircraft",
)
async def api_update_ldnd_monitoring_by_aircraft(
    aircraft_id: int,
    ldnd_id: int,
    data: ldnd_monitoring_schema.LDNDMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an LDNDMonitoring entry for a specific aircraft."""
    existing = await get_ldnd_monitoring_by_aircraft(session, ldnd_id, aircraft_id)
    if not existing:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    updated = await update_ldnd_monitoring(session, ldnd_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return updated


@router_aircraft_scoped.delete(
    "/{aircraft_id}/ldnd-monitoring/{ldnd_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete LDND monitoring for aircraft",
)
async def api_delete_ldnd_monitoring_by_aircraft(
    aircraft_id: int,
    ldnd_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an LDNDMonitoring entry for a specific aircraft."""
    deleted = await soft_delete_ldnd_monitoring_by_aircraft(session, ldnd_id, aircraft_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="LDNDMonitoring not found")
    return None
