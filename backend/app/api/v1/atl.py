"""ATL paged endpoint: GET /api/v1/aircraft/{aircraft_id}/atl/paged with search (sequence_no), filter (nature_of_flight), sort, pagination, and auto_comp_* computed fields. All floats formatted to 2 decimal places."""
from math import ceil
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_account_permission, get_current_active_account
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.database import get_session
from app.models.account import AccountInformation
from app.schemas import aircraft_technical_log_schema
from app.repository.aircraft_technical_log import list_atl_paged
from app.repository.aircraft import get_aircraft
from app.core.atl_derived_times import (
    backfill_atl_auto_fields_for_scope,
    canonical_time_fields_from_auto,
    map_auto_fields_to_comp,
    resolve_auto_fields,
)


def _round_floats_2(obj: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """Recursively round all float values to 2 decimal places (n.2f)."""
    if isinstance(obj, dict):
        return {k: _round_floats_2(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats_2(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 2)
    return obj


router = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["atl"],
)


@router.get("/{aircraft_id}/atl/paged")
async def atl_paged(
    aircraft_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    search: Optional[str] = Query(None, description="Search by sequence_no"),
    nature_of_flight: Optional[str] = Query(None, description="Filter by NATURE OF FLIGHT (e.g. TR, ATL_REPL)"),
    sort: Optional[str] = Query("asc", description="Sort sequence_no: asc or desc"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page: 10, 20, 50, 100"),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated ATL list for aircraft. Path: aircraft_id. Search: sequence_no. Filter: nature_of_flight. Sort: sequence_no asc/desc. Pagination: 10, 20, 50, 100. All floats and auto_comp_* formatted to 2 decimal places."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    if page_size not in (10, 20, 50, 100):
        page_size = 10
    sort_sequence = "desc" if sort and str(sort).strip().lower() == "desc" else "asc"
    offset = (page - 1) * page_size

    items, total = await list_atl_paged(
        session=session,
        limit=page_size,
        offset=offset,
        search=search,
        nature_of_flight=nature_of_flight,
        sort_sequence=sort_sequence,
        aircraft_fk=aircraft_id,
    )

    total = int(total) if total is not None else 0
    pages = int(ceil(total / page_size)) if total else 0
    result_items = []
    auto_fields_memo = {}

    for item in items:
        base = aircraft_technical_log_schema.AircraftTechnicalLogRead.from_orm(item)
        # Use aircraft from get_aircraft (always loaded); not item.aircraft (relationship may be lazy/missing).
        auto_base = await resolve_auto_fields(session, item, aircraft, auto_fields_memo)
        auto_rounded = {k: round(v, 2) for k, v in auto_base.items()}
        auto_comp = {k: round(v, 2) for k, v in map_auto_fields_to_comp(auto_rounded).items()}
        canonical = canonical_time_fields_from_auto(auto_rounded)
        paged_item = aircraft_technical_log_schema.ATLPagedItem.parse_obj(
            {**base.dict(), **canonical, **auto_comp},
        )
        # Apply n.2f for all floats in the response (including base fields and auto_comp)
        result_items.append(_round_floats_2(paged_item.dict()))

    return {
        "items": result_items,
        "total": total,
        "page": int(page),
        "pages": pages,
        "page_size": int(page_size),
    }


@router.post(
    "/{aircraft_id}/atl/backfill-auto-fields",
    summary="Backfill persisted auto_* columns for an aircraft ATL stream",
)
async def backfill_atl_auto_fields(
    aircraft_id: int,
    batch_id: Optional[int] = Query(
        None,
        description="Optional atl_batch.id; omit to backfill rows with NULL atl_batch_fk only.",
    ),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Recompute and persist auto_* for all ATLs on this aircraft (and optional batch)."""
    await ensure_account_permission(
        session, current_account, MAINTENANCE_MODULE, "update"
    )
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    updated = await backfill_atl_auto_fields_for_scope(
        session,
        aircraft_id,
        atl_batch_fk=batch_id,
        aircraft_obj=aircraft,
    )
    await session.commit()
    return {"aircraft_id": aircraft_id, "atl_batch_fk": batch_id, "rows_updated": updated}
