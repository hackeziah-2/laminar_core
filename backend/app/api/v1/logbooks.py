import json
from math import ceil
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    UploadFile,
    File,
    Form,
    status
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import logbook_schema
from app.repository.logbooks import (
    # Engine Logbook
    create_engine_logbook,
    get_engine_logbook,
    list_engine_logbooks,
    update_engine_logbook,
    soft_delete_engine_logbook,
    # Airframe Logbook
    create_airframe_logbook,
    get_airframe_logbook,
    list_airframe_logbooks,
    update_airframe_logbook,
    soft_delete_airframe_logbook,
    # Avionics Logbook
    create_avionics_logbook,
    get_avionics_logbook,
    list_avionics_logbooks,
    update_avionics_logbook,
    soft_delete_avionics_logbook,
    # Propeller Logbook
    create_propeller_logbook,
    get_propeller_logbook,
    list_propeller_logbooks,
    update_propeller_logbook,
    soft_delete_propeller_logbook,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/logbooks",
    tags=["logbooks"]
)


def clean_parsed_data(parsed: dict) -> dict:
    """Convert empty strings to None for optional fields."""
    cleaned = {}
    for key, value in parsed.items():
        if value == "":
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def normalize_logbook_payload(parsed: dict) -> dict:
    """Parse component_parts if JSON string; support componentParts (camelCase)."""
    out = dict(parsed)
    # Accept componentParts (camelCase) as component_parts
    if "componentParts" in out and "component_parts" not in out:
        out["component_parts"] = out.pop("componentParts", None)
    # Parse component_parts if it's a JSON string (common with form/multipart)
    cp = out.get("component_parts")
    if isinstance(cp, str) and cp.strip():
        try:
            out["component_parts"] = json.loads(cp)
        except json.JSONDecodeError:
            pass
    elif isinstance(cp, str) and not cp.strip():
        out["component_parts"] = []
    return out


def _parse_aircraft_fk(value: Optional[str]) -> Optional[int]:
    """Parse aircraft_fk query param; treat empty, '{}', or invalid as None."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "{}"):
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ========== Engine Logbook Endpoints ==========
@router.get(
    "/engine/paged",
    summary="List Engine Logbook entries (paginated)",
    description="Retrieve a paginated list of Engine Logbook entries with optional search and sorting. "
                "Supports filtering by sequence number and description.",
    response_description="Paginated list of Engine Logbook entries"
)
async def api_list_engine_logbooks_paged(
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search in sequence_no and description fields"),
    sort: Optional[str] = Query("", description="Sort fields (comma-separated). Prefix with '-' for descending. Example: -created_at,sequence_no"),
    aircraft_fk: Optional[str] = Query(None, description="Filter by aircraft ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Engine Logbook entries."""
    offset = (page - 1) * limit
    items, total = await list_engine_logbooks(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        aircraft_fk=_parse_aircraft_fk(aircraft_fk),
    )
    pages = ceil(total / limit) if total else 0
    
    items_schemas = [
        logbook_schema.EngineLogbookRead.from_orm(item)
        for item in items
    ]
    
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/engine/{logbook_id}",
    response_model=logbook_schema.EngineLogbookRead,
    summary="Get Engine Logbook entry by ID",
    description="Retrieve a single Engine Logbook entry by its ID. Response includes component_parts. Returns 404 if not found or soft-deleted.",
    response_description="Engine Logbook entry details including component_parts"
)
async def api_get_engine_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Engine Logbook entry by ID."""
    obj = await get_engine_logbook(session, logbook_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Engine Logbook not found"
        )
    return obj


@router.post(
    "/engine",
    response_model=logbook_schema.EngineLogbookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Engine Logbook entry",
    description="Create a new Engine Logbook entry. Required fields: date, sequence_no. "
                "Optional fields: engine_tsn, tach_time, engine_tso, engine_tbo, description, "
                "mechanic_fk, signature, upload_file.",
    response_description="Created Engine Logbook entry"
)
async def api_create_engine_logbook(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session)
):
    """Create a new Engine Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = normalize_logbook_payload(parsed)
        payload = logbook_schema.EngineLogbookCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_engine_logbook(session, payload, upload_file)


@router.put(
    "/engine/{logbook_id}",
    response_model=logbook_schema.EngineLogbookRead,
    summary="Update Engine Logbook entry",
    description="Update an existing Engine Logbook entry. Only provided fields will be updated. "
                "Returns 404 if not found or soft-deleted.",
    response_description="Updated Engine Logbook entry"
)
async def api_update_engine_logbook(
    logbook_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update an Engine Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        parsed = normalize_logbook_payload(parsed)
        logbook_in = logbook_schema.EngineLogbookUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_engine_logbook(
        session=session,
        logbook_id=logbook_id,
        logbook_in=logbook_in,
        upload_file=upload_file,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Engine Logbook not found"
        )

    return updated


@router.delete(
    "/engine/{logbook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete Engine Logbook entry",
    description="Soft delete an Engine Logbook entry (sets is_deleted flag). "
                "The entry will not appear in list queries but remains in the database. "
                "Returns 404 if not found or already deleted.",
    response_description="No content on successful deletion"
)
async def api_delete_engine_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Engine Logbook entry."""
    deleted = await soft_delete_engine_logbook(session, logbook_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engine Logbook not found",
        )
    return None


# ========== Airframe Logbook Endpoints ==========
@router.get("/airframe/paged")
async def api_list_airframe_logbooks_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort: Optional[str] = Query("", description="Example: -created_at,sequence_no"),
    aircraft_fk: Optional[str] = Query(None, description="Filter by aircraft ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Airframe Logbook entries."""
    offset = (page - 1) * limit
    items, total = await list_airframe_logbooks(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        aircraft_fk=_parse_aircraft_fk(aircraft_fk),
    )
    pages = ceil(total / limit) if total else 0
    
    items_schemas = [
        logbook_schema.AirframeLogbookRead.from_orm(item)
        for item in items
    ]
    
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/airframe/{logbook_id}",
    response_model=logbook_schema.AirframeLogbookRead,
    summary="Get Airframe Logbook entry by ID",
    description="Retrieve a single Airframe Logbook entry by its ID. Response includes component_parts. Returns 404 if not found or soft-deleted.",
    response_description="Airframe Logbook entry details including component_parts"
)
async def api_get_airframe_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Airframe Logbook entry by ID."""
    obj = await get_airframe_logbook(session, logbook_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Airframe Logbook not found"
        )
    return obj


@router.post(
    "/airframe",
    response_model=logbook_schema.AirframeLogbookRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create_airframe_logbook(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session)
):
    """Create a new Airframe Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = normalize_logbook_payload(parsed)
        payload = logbook_schema.AirframeLogbookCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_airframe_logbook(session, payload, upload_file)


@router.put(
    "/airframe/{logbook_id}",
    response_model=logbook_schema.AirframeLogbookRead
)
async def api_update_airframe_logbook(
    logbook_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update an Airframe Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        parsed = normalize_logbook_payload(parsed)
        logbook_in = logbook_schema.AirframeLogbookUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_airframe_logbook(
        session=session,
        logbook_id=logbook_id,
        logbook_in=logbook_in,
        upload_file=upload_file,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Airframe Logbook not found"
        )

    return updated


@router.delete(
    "/airframe/{logbook_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def api_delete_airframe_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Airframe Logbook entry."""
    deleted = await soft_delete_airframe_logbook(session, logbook_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airframe Logbook not found",
        )
    return None


# ========== Avionics Logbook Endpoints ==========
@router.get("/avionics/paged")
async def api_list_avionics_logbooks_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort: Optional[str] = Query("", description="Example: -created_at,sequence_no"),
    aircraft_fk: Optional[str] = Query(None, description="Filter by aircraft ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Avionics Logbook entries."""
    offset = (page - 1) * limit
    items, total = await list_avionics_logbooks(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        aircraft_fk=_parse_aircraft_fk(aircraft_fk),
    )
    pages = ceil(total / limit) if total else 0
    
    items_schemas = [
        logbook_schema.AvionicsLogbookRead.from_orm(item)
        for item in items
    ]
    
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/avionics/{logbook_id}",
    response_model=logbook_schema.AvionicsLogbookRead,
    summary="Get Avionics Logbook entry by ID",
    description="Retrieve a single Avionics Logbook entry by its ID. Response includes component_parts. Returns 404 if not found or soft-deleted.",
    response_description="Avionics Logbook entry details including component_parts"
)
async def api_get_avionics_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Avionics Logbook entry by ID."""
    obj = await get_avionics_logbook(session, logbook_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Avionics Logbook not found"
        )
    return obj


@router.post(
    "/avionics",
    response_model=logbook_schema.AvionicsLogbookRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create_avionics_logbook(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session)
):
    """Create a new Avionics Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = normalize_logbook_payload(parsed)
        payload = logbook_schema.AvionicsLogbookCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_avionics_logbook(session, payload, upload_file)


@router.put(
    "/avionics/{logbook_id}",
    response_model=logbook_schema.AvionicsLogbookRead
)
async def api_update_avionics_logbook(
    logbook_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update an Avionics Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        parsed = normalize_logbook_payload(parsed)
        logbook_in = logbook_schema.AvionicsLogbookUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_avionics_logbook(
        session=session,
        logbook_id=logbook_id,
        logbook_in=logbook_in,
        upload_file=upload_file,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Avionics Logbook not found"
        )

    return updated


@router.delete(
    "/avionics/{logbook_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def api_delete_avionics_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Avionics Logbook entry."""
    deleted = await soft_delete_avionics_logbook(session, logbook_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avionics Logbook not found",
        )
    return None


# ========== Propeller Logbook Endpoints ==========
@router.get("/propeller/paged")
async def api_list_propeller_logbooks_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort: Optional[str] = Query("", description="Example: -created_at,sequence_no"),
    aircraft_fk: Optional[str] = Query(None, description="Filter by aircraft ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Propeller Logbook entries."""
    offset = (page - 1) * limit
    items, total = await list_propeller_logbooks(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        aircraft_fk=_parse_aircraft_fk(aircraft_fk),
    )
    pages = ceil(total / limit) if total else 0
    
    items_schemas = [
        logbook_schema.PropellerLogbookRead.from_orm(item)
        for item in items
    ]
    
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/propeller/{logbook_id}",
    response_model=logbook_schema.PropellerLogbookRead
)
async def api_get_propeller_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Propeller Logbook entry by ID."""
    obj = await get_propeller_logbook(session, logbook_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Propeller Logbook not found"
        )
    return obj


@router.post(
    "/propeller",
    response_model=logbook_schema.PropellerLogbookRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create_propeller_logbook(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session)
):
    """Create a new Propeller Logbook entry."""
    try:
        parsed = json.loads(json_data)
        payload = logbook_schema.PropellerLogbookCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_propeller_logbook(session, payload, upload_file)


@router.put(
    "/propeller/{logbook_id}",
    response_model=logbook_schema.PropellerLogbookRead
)
async def api_update_propeller_logbook(
    logbook_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update a Propeller Logbook entry."""
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        logbook_in = logbook_schema.PropellerLogbookUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_propeller_logbook(
        session=session,
        logbook_id=logbook_id,
        logbook_in=logbook_in,
        upload_file=upload_file,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Propeller Logbook not found"
        )

    return updated


@router.delete(
    "/propeller/{logbook_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def api_delete_propeller_logbook(
    logbook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete a Propeller Logbook entry."""
    deleted = await soft_delete_propeller_logbook(session, logbook_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Propeller Logbook not found",
        )
    return None


