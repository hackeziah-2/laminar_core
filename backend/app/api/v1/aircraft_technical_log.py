from math import ceil
from typing import List, Dict, Optional, Any

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
    search_atl_by_sequence_no,
    get_aircraft_technical_log,
    get_latest_aircraft_technical_log,
    create_aircraft_technical_log,
    update_aircraft_technical_log,
    soft_delete_aircraft_technical_log,
    get_previous_atl,
)
from app.database import get_session


def _float_or_zero(value: Any) -> float:
    """Parse value to float; return 0.0 on error or None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if (value == value) else 0.0  # NaN check
    if isinstance(value, str):
        try:
            return float(value.strip()) if value.strip() else 0.0
        except ValueError:
            return 0.0
    return 0.0


def compute_auto_fields(atl, prev_atl, aircraft) -> Dict[str, float]:
    """Compute auto_* fields for one ATL row. Previous = last ATL by sequence_no (same aircraft).
    Airframe Run time = tach_start - tach_end; AFTT = Previous AFTT + run_time.
    Engine/Propeller run time = Airframe run time; TSN/TSO = Previous + run_time; TBO = life_limit - current TSO.
    """
    out = {
        "auto_airframe_run_time": 0.0,
        "auto_airframe_aftt": 0.0,
        "auto_engine_run_time": 0.0,
        "auto_run_time": 0.0,
        "auto_engine_tsn": 0.0,
        "auto_engine_tso": 0.0,
        "auto_engine_tbo": 0.0,
        "auto_propeller_run_time": 0.0,
        "auto_propeller_tsn": 0.0,
        "auto_propeller_tso": 0.0,
        "auto_propeller_tbo": 0.0,
    }
    try:
        tach_start = _float_or_zero(getattr(atl, "tachometer_start", None))
        tach_end = _float_or_zero(getattr(atl, "tachometer_end", None))
        # Airframe Run time = tach start - tach end (per spec)
        out["auto_airframe_run_time"] = tach_start - tach_end
    except Exception:
        pass

    try:
        prev_aftt = _float_or_zero(getattr(prev_atl, "airframe_aftt", None)) if prev_atl else 0.0
        out["auto_airframe_aftt"] = prev_aftt + out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        out["auto_engine_run_time"] = out["auto_airframe_run_time"]
        out["auto_run_time"] = out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        prev_engine_tsn = _float_or_zero(getattr(prev_atl, "engine_tsn", None)) if prev_atl else 0.0
        out["auto_engine_tsn"] = prev_engine_tsn + out["auto_engine_run_time"]
    except Exception:
        pass

    try:
        prev_engine_tso = _float_or_zero(getattr(prev_atl, "engine_tso", None)) if prev_atl else 0.0
        out["auto_engine_tso"] = prev_engine_tso + out["auto_engine_run_time"]
    except Exception:
        pass

    try:
        life_engine = _float_or_zero(getattr(aircraft, "engine_life_time_limit", None)) if aircraft else _float_or_zero(getattr(atl, "life_time_limit_engine", None))
        curr_tso = out["auto_engine_tso"]  # use computed current TSO
        out["auto_engine_tbo"] = life_engine - curr_tso if life_engine else 0.0
    except Exception:
        pass

    try:
        out["auto_propeller_run_time"] = out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        prev_prop_tsn = _float_or_zero(getattr(prev_atl, "propeller_tsn", None)) if prev_atl else 0.0
        out["auto_propeller_tsn"] = prev_prop_tsn + out["auto_propeller_run_time"]
    except Exception:
        pass

    try:
        prev_prop_tso = _float_or_zero(getattr(prev_atl, "propeller_tso", None)) if prev_atl else 0.0
        out["auto_propeller_tso"] = prev_prop_tso + out["auto_propeller_run_time"]
    except Exception:
        pass

    try:
        life_prop = _float_or_zero(getattr(aircraft, "propeller_life_time_limit", None)) if aircraft else _float_or_zero(getattr(atl, "life_time_limit_propeller", None))
        curr_tso = out["auto_propeller_tso"]
        out["auto_propeller_tbo"] = life_prop - curr_tso if life_prop else 0.0
    except Exception:
        pass

    return out

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
    """Get paginated list of Aircraft Technical Log entries with auto_* computed fields.
    Previous values are from the last ATL by sequence_no (same aircraft).
    Auto fields: airframe/engine/propeller run time, AFTT, TSN, TSO, TBO (2 decimal places).
    """
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

    result_items = []
    for item in items:
        base = aircraft_technical_log_schema.AircraftTechnicalLogRead.from_orm(item)
        prev_atl = await get_previous_atl(session, item.aircraft_fk, item.sequence_no)
        aircraft_obj = getattr(item, "aircraft", None)
        auto_fields = compute_auto_fields(item, prev_atl, aircraft_obj)
        auto_fields = {k: round(v, 2) for k, v in auto_fields.items()}
        paged_item = aircraft_technical_log_schema.ATLPagedItemWithAuto(
            **base.dict(),
            **auto_fields,
        )
        result_items.append(paged_item.dict())

    return {
        "items": result_items,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/search",
    response_model=List[aircraft_technical_log_schema.ATLSearchItem]
)
async def api_search_by_sequence(
    search: Optional[str] = Query(None, description="Search by ATL Sequence Number"),
    aircraft_id: Optional[int] = Query(None, description="Filter by aircraft ID (e.g. when on aircraft-scoped TCC form)"),
    session: AsyncSession = Depends(get_session)
):
    """Search by ATL Sequence Number for Sequence No. / ATL Reference (type to search). Accepts 'ATL-24451' or '24451'. Returns id (use as atl_ref), sequence_no, sequence_no_display (e.g. 'ATL-24451' for dropdown label), and aircraft (id, registration, model)."""
    if not search or not str(search).strip():
        return []
    items = await search_atl_by_sequence_no(
        session, search=search.strip(), aircraft_fk=aircraft_id
    )
    return [aircraft_technical_log_schema.ATLSearchItem.from_orm(item) for item in items]


@router.get(
    "/latest",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead
)
async def api_get_latest(
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get the latest Aircraft Technical Log entry by sequence_no."""
    obj = await get_latest_aircraft_technical_log(session, aircraft_fk=aircraft_fk)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="No Aircraft Technical Log entries found"
        )
    return obj


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
