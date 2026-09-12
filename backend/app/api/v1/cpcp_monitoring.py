from typing import Optional, Set

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import Pagination, paged_payload, pagination_params
from app.schemas import cpcp_monitoring_schema
from app.repository.cpcp_monitoring import (
    create_cpcp_monitoring,
    get_cpcp_monitoring,
    list_cpcp_monitorings,
    reorder_cpcp_monitorings,
    update_cpcp_monitoring,
    soft_delete_cpcp_monitoring,
)
from app.api.deps import get_current_active_account
from app.constants.audit import CPCP_MONITORING_MODULE_NAME, CPCP_MONITORING_TABLE_NAME
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.aircraft import get_aircraft
from app.services.cpcp_computation import (
    fetch_latest_atl_metrics_by_aircraft_ids,
    to_cpcp_monitoring_read_sync,
)

router = APIRouter(
    prefix="/api/v1/cpcp-monitoring",
    tags=["cpcp-monitoring"],
)

# Alias matching Excel import key / product naming for reorder.
router_maintenance_cpcp = APIRouter(
    prefix="/api/v1/maintenance-cpcp",
    tags=["cpcp-monitoring"],
)


@router.get("/paged")
async def api_list_paged(
    pagination: Pagination = Depends(pagination_params),
    search: Optional[str] = Query(
        None,
        description="Search by Description or ATL Sequence NO",
    ),
    aircraft_id: Optional[int] = Query(None, description="Filter by aircraft ID"),
    sort: Optional[str] = Query(
        "",
        description=(
            "Sort fields (comma-separated). Prefix '-' for descending. "
            "Example: -created_at,inspection_operation. Default: display_order ascending."
        ),
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of CPCP Monitoring entries. Search by Sequence NO (ATL) and Description. Filter by aircraft_id."""
    items, total = await list_cpcp_monitorings(
        session=session,
        limit=pagination.limit,
        offset=pagination.offset,
        search=search.strip() if search and search.strip() else None,
        sort=sort or "",
        aircraft_id=aircraft_id,
    )
    aircraft_ids: Set[int] = {item.aircraft_id for item in items}
    metrics = await fetch_latest_atl_metrics_by_aircraft_ids(session, aircraft_ids)
    items_schemas = [
        to_cpcp_monitoring_read_sync(
            item,
            tachometer_end=metrics[item.aircraft_id][0],
            airframe_aftt=metrics[item.aircraft_id][1],
        )
        for item in items
    ]
    return paged_payload(
        items_schemas,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def _api_reorder_cpcp_monitorings(
    request: Request,
    payload: cpcp_monitoring_schema.CPCPMonitoringReorderRequest,
    session: AsyncSession,
    current_account: AccountInformation,
):
    return await reorder_cpcp_monitorings(
        session,
        payload.items,
        audit_account_id=current_account.id,
        audit_module_name=CPCP_MONITORING_MODULE_NAME,
        audit_table_name=CPCP_MONITORING_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )


@router.put(
    "/reorder",
    response_model=cpcp_monitoring_schema.CPCPMonitoringReorderResponse,
    summary="Reorder CPCP Monitoring rows",
    description=(
        "Persist drag-and-drop row order for one aircraft. "
        "`items` must list every active CPCP record for that aircraft with "
        "sequential display_order values starting at 1."
    ),
)
@router_maintenance_cpcp.put(
    "/reorder",
    response_model=cpcp_monitoring_schema.CPCPMonitoringReorderResponse,
    summary="Reorder CPCP Monitoring rows",
    description=(
        "Persist drag-and-drop row order for one aircraft. "
        "`items` must list every active CPCP record for that aircraft with "
        "sequential display_order values starting at 1."
    ),
)
async def api_reorder_cpcp_monitorings(
    request: Request,
    payload: cpcp_monitoring_schema.CPCPMonitoringReorderRequest,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Persist CPCP Monitoring display_order arrangement."""
    return await _api_reorder_cpcp_monitorings(
        request, payload, session, current_account
    )


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
    request: Request,
    payload: cpcp_monitoring_schema.CPCPMonitoringCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new CPCP Monitoring entry. aircraft_id is required."""
    aircraft = await get_aircraft(session, payload.aircraft_id)
    if not aircraft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aircraft not found",
        )
    return await create_cpcp_monitoring(
        session,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=CPCP_MONITORING_MODULE_NAME,
        audit_table_name=CPCP_MONITORING_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )


@router.put(
    "/{entry_id}",
    response_model=cpcp_monitoring_schema.CPCPMonitoringRead,
    summary="Update CPCP Monitoring entry",
)
async def api_update(
    request: Request,
    entry_id: int,
    payload: cpcp_monitoring_schema.CPCPMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update a CPCP Monitoring entry. If aircraft_id is provided, it must exist."""
    if payload.aircraft_id is not None:
        aircraft = await get_aircraft(session, payload.aircraft_id)
        if not aircraft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aircraft not found",
            )
    updated = await update_cpcp_monitoring(
        session,
        entry_id,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=CPCP_MONITORING_MODULE_NAME,
        audit_table_name=CPCP_MONITORING_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
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
    request: Request,
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Soft delete a CPCP Monitoring entry."""
    deleted = await soft_delete_cpcp_monitoring(
        session,
        entry_id,
        audit_module_name=CPCP_MONITORING_MODULE_NAME,
        audit_table_name=CPCP_MONITORING_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPCP Monitoring not found",
        )
    return None
