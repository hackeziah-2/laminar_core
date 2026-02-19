import json

from math import ceil
from typing import List, Dict
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
from fastapi.responses import StreamingResponse

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_schema, aircraft_technical_log_schema
from app.repository.aircraft import (
    list_aircraft,
    get_aircraft,
    create_aircraft_with_file,
    update_aircraft_with_file,
    soft_delete_aircraft
)
from app.repository.aircraft_technical_log import search_atl_by_sequence_no
from app.database import get_session
from app.services.generate_report_excel import generate_excel
from app.services.generate_report_pdf import generate_pdf_report

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircrafts"])

@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100), 
    page: int = Query(1, ge=1), 
    search: Optional[str] = None, 
    status: aircraft_schema.AircrarftStatus | None = Query(
        None, description="Filter by status", enum=["active", "inactive", "maintenance"]),
    sort: Optional[str] = "",
    session: AsyncSession = Depends(get_session)
):
    offset = (page - 1) * limit
    items, total = await list_aircraft(session,limit=limit, offset=offset, search=search, status=status, sort=sort)
    pages = ceil(total / limit) if total else 0
    return {"items": items, "total": total, "page": page, "pages": pages}

@router.get(
    "/{aircraft_id}/atl/",
    response_model=List[aircraft_technical_log_schema.ATLSearchItem],
    summary="Search ATL by sequence number (aircraft-scoped)",
    description="Use GET /api/v1/aircraft-technical-log/search?search={sequence_no}&aircraft_id={id} instead. Returns same shape: id (atl_ref), sequence_no, aircraft.",
)
async def api_aircraft_atl_search(
    aircraft_id: int,
    sequence_number: Optional[str] = Query(None, description="Search by ATL sequence number"),
    session: AsyncSession = Depends(get_session),
):
    """[Compatibility] Search ATL by sequence number for this aircraft. Prefer /api/v1/aircraft-technical-log/search?search={sequence_no}&aircraft_id={id} for new code."""
    if not sequence_number or not str(sequence_number).strip():
        return []
    items = await search_atl_by_sequence_no(
        session, search=sequence_number.strip(), aircraft_fk=aircraft_id
    )
    return [aircraft_technical_log_schema.ATLSearchItem.from_orm(item) for item in items]


@router.get("/{aircraft_id}", response_model=aircraft_schema.AircraftOut)
async def api_get(aircraft_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_aircraft(session, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return obj

@router.post("/", response_model=aircraft_schema.AircraftOut)
async def api_create_aircraft_with_file(
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):  
    
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftCreate(**parsed)

    return await create_aircraft_with_file(
        session=session,
        data=aircraft_data,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file
    )

@router.put("/{aircraft_id}", response_model=aircraft_schema.AircraftOut)
async def api_update_aircraft_with_file(
    aircraft_id: int,
    json_data: str = Form(...),
    engine_arc_file: UploadFile = File(None),
    propeller_arc_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):  
    parsed = json.loads(json_data)
    aircraft_data = aircraft_schema.AircraftUpdate(**parsed)
    return await update_aircraft_with_file(
        session=session,
        aircraft_id=aircraft_id,
        data=aircraft_data,
        engine_file=engine_arc_file,
        propeller_file=propeller_arc_file,
    )


@router.delete(
    "/{aircraft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete aircraft",
    description="Soft delete aircraft and all connected data (logbook entries, ATL, LDND, AD, TCC, documents, CPCP, engine/airframe/avionics/propeller logbooks). Sets is_deleted=True in a single transaction.",
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
    headers = ["AC REG", "AIRCRAFT TYPE", "MODEL", "MSN", "BASE LOCATION", "STATUS", "CREATED AT"]
    data_rows = [
        [
            ac["registration"],
            ac["type"],
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