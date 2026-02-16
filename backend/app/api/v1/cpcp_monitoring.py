from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import cpcp_monitoring_schema
from app.repository.cpcp_monitoring import (
    create_cpcp_monitoring,
    get_cpcp_monitoring,
    list_cpcp_monitorings,
    update_cpcp_monitoring,
    soft_delete_cpcp_monitoring,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/cpcp-monitoring",
    tags=["cpcp-monitoring"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(
        None,
        description="Search by Description or ATL Sequence NO",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort fields (comma-separated). Prefix '-' for descending. Example: -created_at,inspection_operation",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of CPCP Monitoring entries. Search by Sequence NO (ATL) and Description."""
    offset = (page - 1) * limit
    items, total = await list_cpcp_monitorings(
        session=session,
        limit=limit,
        offset=offset,
        search=search.strip() if search and search.strip() else None,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [
        cpcp_monitoring_schema.CPCPMonitoringRead.from_orm(item)
        for item in items
    ]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/{entry_id}",
    response_model=cpcp_monitoring_schema.CPCPMonitoringRead,
    summary="Get CPCP Monitoring by ID",
)
async def api_get(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single CPCP Monitoring entry by ID."""
    obj = await get_cpcp_monitoring(session, entry_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="CPCP Monitoring not found",
        )
    return obj


@router.post(
    "/",
    response_model=cpcp_monitoring_schema.CPCPMonitoringRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create CPCP Monitoring entry",
)
async def api_create(
    payload: cpcp_monitoring_schema.CPCPMonitoringCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new CPCP Monitoring entry."""
    return await create_cpcp_monitoring(session, payload)


@router.put(
    "/{entry_id}",
    response_model=cpcp_monitoring_schema.CPCPMonitoringRead,
    summary="Update CPCP Monitoring entry",
)
async def api_update(
    entry_id: int,
    payload: cpcp_monitoring_schema.CPCPMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a CPCP Monitoring entry."""
    updated = await update_cpcp_monitoring(session, entry_id, payload)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="CPCP Monitoring not found",
        )
    return updated


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete CPCP Monitoring entry",
)
async def api_delete(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a CPCP Monitoring entry."""
    deleted = await soft_delete_cpcp_monitoring(session, entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPCP Monitoring not found",
        )
    return None
