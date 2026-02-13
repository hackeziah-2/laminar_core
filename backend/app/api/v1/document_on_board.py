import json
from math import ceil
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
)
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import document_on_board_schema
from app.repository.document_on_board import (
    create_document_on_board,
    get_document_on_board,
    get_document_on_board_by_aircraft,
    list_documents_on_board,
    update_document_on_board,
    soft_delete_document_on_board,
    soft_delete_document_on_board_by_aircraft,
)
from app.repository.aircraft import get_aircraft
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/documents-on-board",
    tags=["documents-on-board"]
)

# Aircraft-scoped router: /api/v1/aircraft/{aircraft_id}/documents-on-board/...
router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["documents-on-board"]
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


@router.get("/paged")
async def api_list_documents_on_board_paged(
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search in document_name, description, and aircraft registration"),
    aircraft_id: Optional[int] = Query(None, description="Filter by aircraft ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: Optional[str] = Query("", description="Sort fields (comma-separated). Prefix with '-' for descending. Example: -created_at,document_name"),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of DocumentOnBoard entries."""
    offset = (page - 1) * limit
    search_param = search.strip() if search and search.strip() else None
    items, total = await list_documents_on_board(
        session=session,
        limit=limit,
        offset=offset,
        search=search_param,
        aircraft_id=aircraft_id,
        status=status,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    
    items_schemas = [
        document_on_board_schema.DocumentOnBoardRead.from_orm(item)
        for item in items
    ]
    
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/{document_id}",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    summary="Get DocumentOnBoard entry by ID",
    description="Retrieve a single DocumentOnBoard entry by its ID. Returns 404 if not found or soft-deleted.",
    response_description="DocumentOnBoard entry details"
)
async def api_get_document_on_board(
    document_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single DocumentOnBoard entry by ID."""
    obj = await get_document_on_board(session, document_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="DocumentOnBoard not found"
        )
    return obj


@router.post(
    "/",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create DocumentOnBoard entry",
    description="Create a new DocumentOnBoard entry. Required: aircraft_id, document_name, issue_date. "
                "Optional: description, expiry_date, warning_days, status, file_path, web_link, is_aircraft_certificate. "
                "Send JSON as 'json_data' form field and optional file as 'upload_file'.",
    response_description="Created DocumentOnBoard entry"
)
async def api_create_document_on_board(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session)
):
    """Create a new DocumentOnBoard entry."""
    try:
        parsed = json.loads(json_data)
        payload = document_on_board_schema.DocumentOnBoardCreate(**parsed)
        return await create_document_on_board(session, payload, upload_file)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {e.json()}" if hasattr(e, 'json') else str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create document: {str(e)}")


@router.put(
    "/{document_id}",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    summary="Update DocumentOnBoard entry",
    description="Update an existing DocumentOnBoard entry. Only provided fields will be updated. "
                "Returns 404 if not found or soft-deleted.",
    response_description="Updated DocumentOnBoard entry"
)
async def api_update_document_on_board(
    document_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update a DocumentOnBoard entry."""
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        document_in = document_on_board_schema.DocumentOnBoardUpdate(**parsed)
        updated = await update_document_on_board(
            session=session,
            document_id=document_id,
            document_in=document_in,
            upload_file=upload_file,
        )

        if not updated:
            raise HTTPException(
                status_code=404,
                detail="DocumentOnBoard not found"
            )

        return updated
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {e.json()}" if hasattr(e, 'json') else str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update document: {str(e)}")


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete DocumentOnBoard entry",
    description="Soft delete a DocumentOnBoard entry (sets is_deleted flag). "
                "The entry will not appear in list queries but remains in the database. "
                "Returns 404 if not found or already deleted.",
    response_description="No content on successful deletion"
)
async def api_delete_document_on_board(
    document_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete a DocumentOnBoard entry."""
    deleted = await soft_delete_document_on_board(session, document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DocumentOnBoard not found",
        )
    return None


# ========== Aircraft-scoped endpoints ==========

@router_aircraft_scoped.get(
    "/{aircraft_id}/documents-on-board/paged",
    summary="List documents for aircraft (paginated)",
    description="Get paginated list of DocumentOnBoard entries for a specific aircraft.",
)
async def api_list_documents_on_board_by_aircraft_paged(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of documents for a specific aircraft."""
    # Verify aircraft exists
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    search_param = search.strip() if search and search.strip() else None
    items, total = await list_documents_on_board(
        session=session,
        limit=limit,
        offset=offset,
        search=search_param,
        aircraft_id=aircraft_id,
        status=status,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [
        document_on_board_schema.DocumentOnBoardRead.from_orm(item)
        for item in items
    ]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.get(
    "/{aircraft_id}/documents-on-board/{document_id}",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    summary="Get document by ID for aircraft",
)
async def api_get_document_on_board_by_aircraft(
    aircraft_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single DocumentOnBoard entry by ID for a specific aircraft."""
    obj = await get_document_on_board_by_aircraft(session, document_id, aircraft_id)
    if not obj:
        raise HTTPException(status_code=404, detail="DocumentOnBoard not found")
    return obj


@router_aircraft_scoped.post(
    "/{aircraft_id}/documents-on-board/",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create document for aircraft",
)
async def api_create_document_on_board_by_aircraft(
    aircraft_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Create a new DocumentOnBoard entry for a specific aircraft."""
    aircraft = await get_aircraft(session, aircraft_id)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    try:
        parsed = json.loads(json_data)
        parsed["aircraft_id"] = aircraft_id  # Override with path aircraft_id
        payload = document_on_board_schema.DocumentOnBoardCreate(**parsed)
        return await create_document_on_board(session, payload, upload_file)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {e.json()}" if hasattr(e, "json") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create document: {str(e)}")


@router_aircraft_scoped.put(
    "/{aircraft_id}/documents-on-board/{document_id}",
    response_model=document_on_board_schema.DocumentOnBoardRead,
    summary="Update document for aircraft",
)
async def api_update_document_on_board_by_aircraft(
    aircraft_id: int,
    document_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update a DocumentOnBoard entry for a specific aircraft."""
    # Verify document belongs to aircraft
    existing = await get_document_on_board_by_aircraft(session, document_id, aircraft_id)
    if not existing:
        raise HTTPException(status_code=404, detail="DocumentOnBoard not found")
    try:
        parsed = json.loads(json_data)
        parsed = clean_parsed_data(parsed)
        document_in = document_on_board_schema.DocumentOnBoardUpdate(**parsed)
        updated = await update_document_on_board(
            session=session,
            document_id=document_id,
            document_in=document_in,
            upload_file=upload_file,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="DocumentOnBoard not found")
        return updated
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {e.json()}" if hasattr(e, "json") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update document: {str(e)}")


@router_aircraft_scoped.delete(
    "/{aircraft_id}/documents-on-board/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete document for aircraft",
)
async def api_delete_document_on_board_by_aircraft(
    aircraft_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a DocumentOnBoard entry for a specific aircraft."""
    deleted = await soft_delete_document_on_board_by_aircraft(
        session, document_id, aircraft_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DocumentOnBoard not found",
        )
    return None
