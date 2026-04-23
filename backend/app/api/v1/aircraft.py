import json
from pathlib import Path

from math import ceil
from typing import Dict, List, Optional, Tuple
from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    UploadFile,
    File,
    Form,
    Depends,
    status
)
from fastapi.responses import StreamingResponse, FileResponse

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_schema, aircraft_technical_log_schema
from app.schemas.aircraft_history_schema import AircraftUpdateWithHistoryResponse
from app.repository.aircraft import (
    list_aircraft,
    list_aircraft_minimal,
    get_aircraft,
    get_aircraft_raw,
    create_aircraft_with_file,
    soft_delete_aircraft,
)
from app.services.aircraft_history_service import (
    list_aircraft_history_paged,
    update_aircraft_and_log_history,
    update_aircraft_with_history as update_aircraft_with_history_service,
)
from app.repository.aircraft_technical_log import (
    search_atl_by_sequence_no,
    get_latest_aircraft_technical_log,
)
from app.core.atl_derived_times import resolve_auto_fields, map_auto_fields_to_comp
from app.database import get_session
from app.api.deps import get_current_active_account
from app.models.account import AccountInformation
from app.upload_config import UPLOAD_DIR
from app.services.generate_report_excel import generate_excel
from app.services.generate_report_pdf import generate_pdf_report

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircrafts"])


@router.get("/list", response_model=List[aircraft_schema.AircraftListItem])
async def api_list_aircraft(session: AsyncSession = Depends(get_session)):
    items = await list_aircraft_minimal(session)
    return [aircraft_schema.AircraftListItem.from_orm(item) for item in items]

@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, description="Search in registration, base, model"),
    status: Optional[str] = Query(
        None,
        description="Filter by status: 'all' or omit for all; 'active', 'inactive', 'maintenance' for specific status",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort: field name or -field for desc, comma-separated (e.g. registration,-created_at)",
    ),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    search_param = search.strip() if (search and isinstance(search, str)) else None
    status_param = status.strip() if (status and isinstance(status, str)) else None
    sort_param = (sort.strip() if (sort and isinstance(sort, str)) else None) or ""
    items, total = await list_aircraft(
        session, limit=limit, offset=offset, search=search_param, status=status_param, sort=sort_param
    )
    pages = ceil(total / limit) if limit else 0
    items_out = [aircraft_schema.AircraftOut.from_orm(a) for a in items]
    return {"items": items_out, "total": total, "page": page, "pages": pages}

@router.get(
    "/{aircraft_id}/atl/",
    response_model=List[aircraft_technical_log_schema.ATLAircraftScopedSearchItem],
    summary="Search ATL by sequence number (aircraft-scoped)",
    description=(
        "Returns matching rows for this aircraft: id (atl_ref), sequence_no, tachometer_end, "
        "auto_airframe_aftt (cumulative, same rules as GET …/atl/paged), origin_date. "
        "For dropdown label + aircraft only, use GET /api/v1/aircraft-technical-log/search."
    ),
)
async def api_aircraft_atl_search(
    aircraft_id: int,
    sequence_number: Optional[str] = Query(None, description="Search by ATL sequence number"),
    session: AsyncSession = Depends(get_session),
):
    """Search ATL by sequence number for this aircraft; each hit includes tach end, computed AFTT, and origin date."""
    if not sequence_number or not str(sequence_number).strip():
        return []
    items = await search_atl_by_sequence_no(
        session, search=sequence_number.strip(), aircraft_fk=aircraft_id
    )
    memo: Dict[Tuple[int, str], Dict[str, float]] = {}
    out: List[aircraft_technical_log_schema.ATLAircraftScopedSearchItem] = []
    for item in items:
        aircraft_obj = getattr(item, "aircraft", None)
        auto = await resolve_auto_fields(session, item, aircraft_obj, memo)
        out.append(
            aircraft_technical_log_schema.ATLAircraftScopedSearchItem(
                id=item.id,
                sequence_no=str(item.sequence_no).strip() if item.sequence_no is not None else "",
                tachometer_end=_round_optional_float_2(item.tachometer_end),
                auto_airframe_aftt=_round_optional_float_2(auto.get("auto_airframe_aftt")),
                origin_date=item.origin_date,
            )
        )
    return out


def _round_optional_float_2(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


@router.get(
    "/{aircraft_id}/details/",
    response_model=aircraft_schema.AircraftDetailsResponse,
    summary="Aircraft details and latest ATL",
    description=(
        "Returns identification fields for the aircraft and the latest non-deleted ATL "
        "(highest sequence_no). ATL time fields use the same cumulative auto_* rules as "
        "GET …/atl/paged (airframe_aftt from auto_comp_airframe_aftt; engine/prop times from auto_engine_* / auto_propeller_*)."
    ),
)
async def api_aircraft_details(
    aircraft_id: int,
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft_raw(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    summary = aircraft_schema.AircraftDetailsSummary(
        aircraft_id=aircraft.id,
        registration=aircraft.registration,
        msn=aircraft.msn,
        engine_serial_number=aircraft.engine_serial_number,
        propeller_serial_number=aircraft.propeller_serial_number,
    )

    latest = await get_latest_aircraft_technical_log(session, aircraft_fk=aircraft_id)
    atl_block = None
    if latest is not None:
        auto_base = await resolve_auto_fields(session, latest, aircraft)
        auto_rounded = {k: round(v, 2) for k, v in auto_base.items()}
        auto_comp = {k: round(v, 2) for k, v in map_auto_fields_to_comp(auto_rounded).items()}
        atl_block = aircraft_schema.AircraftDetailsATLBlock(
            tachometer_end=_round_optional_float_2(latest.tachometer_end),
            airframe_aftt=auto_comp.get("auto_comp_airframe_aftt"),
            engine_tsn=auto_rounded.get("auto_engine_tsn"),
            engine_tbo=auto_rounded.get("auto_engine_tbo"),
            engine_tso=auto_rounded.get("auto_engine_tso"),
            propeller_tsn=auto_rounded.get("auto_propeller_tsn"),
            propeller_tbo=auto_rounded.get("auto_propeller_tbo"),
            propeller_tso=auto_rounded.get("auto_propeller_tso"),
            sequence_no=str(latest.sequence_no).strip() if latest.sequence_no is not None else "",
        )

    return aircraft_schema.AircraftDetailsResponse(aircraft=summary, atl=atl_block)


@router.get("/{aircraft_id}", response_model=aircraft_schema.AircraftOut)
async def api_get(aircraft_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_aircraft(session, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return obj


@router.get("/{aircraft_id}/history")
async def api_get_aircraft_history(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    obj = await get_aircraft(session, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    items, total = await list_aircraft_history_paged(
        session,
        aircraft_id,
        limit=limit,
        offset=offset,
    )
    pages = ceil(total / limit) if total else 0
    return {"items": items, "total": total, "page": page, "pages": pages}


def _serve_aircraft_file(
    file_path: Optional[str],
    filename_for_response: str,
    disposition: str = "attachment",
) -> FileResponse:
    """Resolve aircraft file path under UPLOAD_DIR and return FileResponse or raise 404."""
    if not file_path or not str(file_path).strip():
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(file_path).resolve()
    upload_root = Path(UPLOAD_DIR).resolve()
    if not path.is_file() or not str(path).startswith(str(upload_root)):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{path.name}"'},
    )


@router.get(
    "/{aircraft_id}/files/engine-arc",
    summary="Engine ARC: Download or View",
    description=(
        "**Download:** Call with no query (or disposition=attachment) to get the file as attachment. "
        "**View:** Call with ?disposition=inline to display in browser (use for modal/preview when engine_arc_is_image is true)."
    ),
    response_description="File content",
    tags=["aircrafts"],
)
async def api_download_engine_arc(
    aircraft_id: int,
    disposition: Optional[str] = Query("attachment", description="'attachment' = Download; 'inline' = View in browser/modal"),
    session: AsyncSession = Depends(get_session),
):
    """Engine ARC: Download (attachment) or View (inline for modal)."""
    raw = await get_aircraft_raw(session, aircraft_id)
    if not raw or not getattr(raw, "engine_arc", None):
        raise HTTPException(status_code=404, detail="Engine ARC file not found")
    disp = "inline" if (disposition or "").strip().lower() == "inline" else "attachment"
    return _serve_aircraft_file(raw.engine_arc, "engine-arc", disp)


@router.get(
    "/{aircraft_id}/files/propeller-arc",
    summary="Propeller ARC: Download or View",
    description=(
        "**Download:** Call with no query (or disposition=attachment) to get the file as attachment. "
        "**View:** Call with ?disposition=inline to display in browser (use for modal/preview when propeller_arc_is_image is true)."
    ),
    response_description="File content",
    tags=["aircrafts"],
)
async def api_download_propeller_arc(
    aircraft_id: int,
    disposition: Optional[str] = Query("attachment", description="'attachment' = Download; 'inline' = View in browser/modal"),
    session: AsyncSession = Depends(get_session),
):
    """Propeller ARC: Download (attachment) or View (inline for modal)."""
    raw = await get_aircraft_raw(session, aircraft_id)
    if not raw or not getattr(raw, "propeller_arc", None):
        raise HTTPException(status_code=404, detail="Propeller ARC file not found")
    disp = "inline" if (disposition or "").strip().lower() == "inline" else "attachment"
    return _serve_aircraft_file(raw.propeller_arc, "propeller-arc", disp)


@router.post(
    "/",
    response_model=aircraft_schema.AircraftOut,
    summary="Create aircraft",
    description="Create a new aircraft. Also creates a FleetDailyUpdate (one-to-one with aircraft) with status RUNNING.",
)
async def api_create_aircraft_with_file(
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftCreate(**parsed)

    return await create_aircraft_with_file(
        session=session,
        data=aircraft_data,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file,
        audit_account_id=current_account.id,
    )

@router.put("/{aircraft_id}", response_model=aircraft_schema.AircraftOut)
async def api_update_aircraft_with_file(
    aircraft_id: int,
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):  
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftUpdate(**parsed)
    return await update_aircraft_and_log_history(
        session=session,
        aircraft_id=aircraft_id,
        data=aircraft_data,
        user_id=current_account.id,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file,
    )


@router.post("/{aircraft_id}/update-with-history", response_model=AircraftUpdateWithHistoryResponse)
async def api_update_aircraft_with_history(
    aircraft_id: int,
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftUpdate(**parsed)
    return await update_aircraft_with_history_service(
        session=session,
        aircraft_id=aircraft_id,
        data=aircraft_data,
        user_id=current_account.id,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file,
    )


@router.delete(
    "/{aircraft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete aircraft",
    description="Soft delete aircraft and all connected data (logbook entries, ATL, LDND, AD, TCC, documents, CPCP, fleet daily update, engine/airframe/avionics/propeller logbooks). Sets is_deleted=True in a single transaction.",
)
async def api_delete_aircraft(aircraft_id: int, session: AsyncSession = Depends(get_session)):
    deleted = await soft_delete_aircraft(session, aircraft_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aircraft not found",
        )
    return None

# @router.delete("/{flight_id}")
# async def api_delete(flight_id: int, session: AsyncSession = Depends(get_session)):
#     deleted = await delete_flight(session, flight_id)
#     if not deleted:
#         raise HTTPException(status_code=404, detail="Flight not found")
#     return {"ok": True}


#reports
@router.post("/reports/excel")
async def export_excel(data: List[Dict]):

    title = "Aircraft Report"
    file = generate_excel(data, title)
    return StreamingResponse(
        file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=report_aircraft.xlsx"},
    )

@router.post("/reports/pdf")
def export_pdf(aircraft_data: List[Dict]):
    # Prepare headers and rows dynamically
    headers = ["AC REG", "MODEL", "MSN", "BASE LOCATION", "STATUS", "CREATED AT"]
    data_rows = [
        [
            ac["registration"],
            ac["model"],
            ac["msn"],
            ac["base"],
            ac["status"],
            ac["created_at"].split("T")[0]
        ]
        for ac in aircraft_data
    ]
    
    pdf_file = generate_pdf_report("Aircraft Report", headers, data_rows, header_color="#007BFF")
    
    return StreamingResponse(
        pdf_file,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=aircraft_report.pdf"},
    )
