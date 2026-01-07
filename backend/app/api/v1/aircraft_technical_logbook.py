import json

from math import ceil
from typing import List, Dict
from app.repository.aircraft_technical_logbook import (
    list_aircraft_logbook_entries, list_aircraft_has_logbook_entries
)
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

from app.schemas.aircraft_technical_logbook  import (
    AircraftLogbookEntryBase,
    AircraftLogbookEntryCreate,
    AircraftLogbookEntryRead,
    AircraftLogbookEntryUpdate
)
from app.repository.aircraft_technical_logbook import (
   create_logbook_entry,
   get_logbook_entry,
   update_logbook_entry
)
from app.database import get_session

from app.services.generate_report_excel import generate_excel
from app.services.generate_report_pdf import generate_pdf_report

router = APIRouter(prefix="/api/v1/aircraft-technical-logbook", tags=["Aircraft-technical-logbook"])

@router.post("", response_model = AircraftLogbookEntryCreate, status_code=201)
async def create_aircraft_logbook(
        payload: AircraftLogbookEntryCreate, 
        session: AsyncSession = Depends(get_session)
    ):
    return await create_logbook_entry(session, payload)

@router.get("/{logbook_id:int}", response_model=AircraftLogbookEntryRead)
async def api_get_atl(logbook_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_logbook_entry(session, logbook_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return obj

@router.put(
    "/{logbook_entry_id}",
    response_model=AircraftLogbookEntryRead,
)
async def api_update_logbook_entry(
    logbook_entry_id: int,
    logbook_entry_in: AircraftLogbookEntryUpdate,
    session: AsyncSession = Depends(get_session),
):
    updated = await update_logbook_entry(
        session=session,
        logbook_entry_id=logbook_entry_id,
        logbook_entry_in=logbook_entry_in,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Logbook entry not found")

    return updated


@router.get("/paged")
async def api_list_aircraft_logbook_entries_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, description="Search by sequence_no"),
    sort: Optional[str] = Query(
        "",
        description="Example: -created_at,sequence_no"
    ),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit

    items, total = await list_aircraft_logbook_entries(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )

    pages = ceil(total / limit) if total else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
    }
    
# @router.get(
#     "/{aircraft_id}/",
#     response_model=dict
# )
# async def api_list_aircraft_has_logbook_entries_paged(
#     aircraft_id: int,
#     limit: int = Query(10, ge=1, le=100),
#     page: int = Query(1, ge=1),
#     search: Optional[str] = None,
#     sort: Optional[str] = "",
#     session: AsyncSession = Depends(get_session),
# ):
#     offset = (page - 1) * limit

#     items, total = await list_aircraft_has_logbook_entries(
#         session=session,
#         aircraft_id=aircraft_id,
#         limit=limit,
#         offset=offset,
#         search=search,
#         sort=sort,
#     )

#     pages = ceil(total / limit) if total else 0

#     return {
#         "items": items,
#         "total": total,
#         "page": page,
#         "pages": pages,
#     }
