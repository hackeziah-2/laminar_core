"""ATL paged endpoint: GET /api/v1/aircraft/{aircraft_id}/atl/paged with search (sequence_no), filter (nature_of_flight), sort, pagination, and auto_comp_* computed fields. All floats formatted to 2 decimal places."""
from math import ceil
from typing import Optional, Dict, Any, List, Union

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import aircraft_technical_log_schema
from app.repository.aircraft_technical_log import list_atl_paged, get_previous_atl
from app.repository.aircraft import get_aircraft


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


def compute_auto_comp(
    atl,
    prev_atl,
    aircraft,
) -> Dict[str, float]:
    """Compute auto_comp_* for one ATL row. Returns 0.0 on error.

    Current ATL (atl) - data applied:
      - tachometer_start, tachometer_end  → airframe_run_time (tach start - tach end), then used as Airframe/Engine/Propeller run time
      - engine_tso                       → engine_tbo = aircraft.engine_life_time_limit - engine_tso
      - propeller_tso                    → propeller_tbo = aircraft.propeller_life_time_limit - propeller_tso

    Previous ATL (prev_atl) = row with latest sequence_no < current sequence_no (same aircraft):
      - airframe_aftt, engine_tsn, engine_tso, propeller_tsn, propeller_tso

    Aircraft: engine_life_time_limit, propeller_life_time_limit
    """
    out = {
        "auto_comp_airframe_run_time": 0.0,
        "auto_comp_airframe_aftt": 0.0,
        "auto_comp_engine_run_time": 0.0,
        "auto_comp_engine_tsn": 0.0,
        "auto_comp_engine_tso": 0.0,
        "auto_comp_engine_tbo": 0.0,
        "auto_comp_propeller_run_time": 0.0,
        "auto_comp_propeller_tsn": 0.0,
        "auto_comp_propeller_tso": 0.0,
        "auto_comp_propeller_tbo": 0.0,
    }
    # auto_comp_airframe_run_time = tach start - tach end
    try:
        tach_start = _float_or_zero(getattr(atl, "tachometer_start", None))
        tach_end = _float_or_zero(getattr(atl, "tachometer_end", None))
        out["auto_comp_airframe_run_time"] = tach_start - tach_end
    except Exception:
        pass

    # auto_comp_airframe_aftt = Previous Airframe AFTT + Airframe current run time
    try:
        prev_aftt = _float_or_zero(getattr(prev_atl, "airframe_aftt", None)) if prev_atl else 0.0
        curr_run = out["auto_comp_airframe_run_time"]
        out["auto_comp_airframe_aftt"] = prev_aftt + curr_run
    except Exception:
        pass

    # auto_comp_engine_run_time = Airframe Run Time
    try:
        out["auto_comp_engine_run_time"] = out["auto_comp_airframe_run_time"]
    except Exception:
        pass

    # auto_comp_engine_tsn = Previous Engine TSN + Engine Current Run Time
    try:
        prev_engine_tsn = _float_or_zero(getattr(prev_atl, "engine_tsn", None)) if prev_atl else 0.0
        curr_run = out["auto_comp_engine_run_time"]
        out["auto_comp_engine_tsn"] = prev_engine_tsn + curr_run
    except Exception:
        pass

    # auto_comp_engine_tso = Previous Engine TSO + Engine Current run time
    try:
        prev_engine_tso = _float_or_zero(getattr(prev_atl, "engine_tso", None)) if prev_atl else 0.0
        curr_run = out["auto_comp_engine_run_time"]
        out["auto_comp_engine_tso"] = prev_engine_tso + curr_run
    except Exception:
        pass

    # auto_comp_engine_tbo = life_time_limit_engine (from aircraft) - ENGINE CURRENT TSO
    try:
        life_engine = _float_or_zero(getattr(aircraft, "engine_life_time_limit", None)) if aircraft else 0.0
        curr_tso = _float_or_zero(getattr(atl, "engine_tso", None))
        curent_id = _float_or_zero(getattr(atl, "id", None))
        print(curent_id, "curent_id")
        print(life_engine, "life_engine_life_enginelife_engine")
        print(curr_tso if life_engine else 0.0, "ldldll")
        print(life_engine - curr_tso if life_engine else 0.0,  "total")
        out["auto_comp_engine_tbo"] = life_engine - curr_tso if life_engine else 0.0
    except Exception:
        pass

    # auto_comp_propeller_run_time = Airframe Run Time
    try:
        out["auto_comp_propeller_run_time"] = out["auto_comp_airframe_run_time"]
    except Exception:
        pass

    # auto_comp_propeller_tsn = Previous Propeller TSN + Propeller Run Time
    try:
        prev_prop_tsn = _float_or_zero(getattr(prev_atl, "propeller_tsn", None)) if prev_atl else 0.0
        curr_run = out["auto_comp_propeller_run_time"]
        out["auto_comp_propeller_tsn"] = prev_prop_tsn + curr_run
    except Exception:
        pass

    # auto_comp_propeller_tso = Previous Propeller TSO + Propeller Run Time
    try:
        prev_prop_tso = _float_or_zero(getattr(prev_atl, "propeller_tso", None)) if prev_atl else 0.0
        curr_run = out["auto_comp_propeller_run_time"]
        out["auto_comp_propeller_tso"] = prev_prop_tso + curr_run
    except Exception:
        pass

    # auto_comp_propeller_tbo = life_time_limit_propeller (from aircraft) - Propeller current TSO
    try:
        life_prop = _float_or_zero(getattr(aircraft, "propeller_life_time_limit", None)) if aircraft else 0.0
        curr_tso = _float_or_zero(getattr(atl, "propeller_tso", None))
        out["auto_comp_propeller_tbo"] = life_prop - curr_tso if life_prop else 0.0
    except Exception:
        pass

    return out


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

    for item in items:
        base = aircraft_technical_log_schema.AircraftTechnicalLogRead.from_orm(item)
        prev_atl = await get_previous_atl(session, item.aircraft_fk, item.sequence_no)
        aircraft_obj = getattr(item, "aircraft", None)
        auto_comp = compute_auto_comp(item, prev_atl, aircraft_obj)
        # Round all auto_comp to 2 decimals
        auto_comp = {k: round(v, 2) for k, v in auto_comp.items()}
        paged_item = aircraft_technical_log_schema.ATLPagedItem(
            **base.dict(),
            **auto_comp,
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
