import json
from math import ceil
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status,
    Form,
    File,
    UploadFile,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import aircraft_statutory_certificate_schema
from app.schemas.aircraft_statutory_certificate_schema import CategoryTypeEnum
from app.repository.aircraft_statutory_certificate import (
    list_aircraft_statutory_certificates,
    get_aircraft_statutory_certificate,
    get_aircraft_statutory_certificate_by_aircraft,
    create_aircraft_statutory_certificate,
    update_aircraft_statutory_certificate,
    soft_delete_aircraft_statutory_certificate,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/aircraft-statutory-certificates",
    tags=["aircraft-statutory-certificates"],
)
router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["aircraft-statutory-certificates"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    aircraft_fk: Optional[int] = Query(None),
    category_type: Optional[CategoryTypeEnum] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """List aircraft statutory certificates with pagination and filter by category_type."""
    offset = (page - 1) * limit
    items, total = await list_aircraft_statutory_certificates(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_fk,
        category_type=category_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{cert_id}", response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead)
async def api_get(
    cert_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single aircraft statutory certificate by ID."""
    obj = await get_aircraft_statutory_certificate(session, cert_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead.from_orm(obj)


@router.post(
    "/",
    response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Create a new aircraft statutory certificate. Send JSON as 'json_data' and optional file as 'upload_file'."""
    try:
        parsed = json.loads(json_data)
        payload = aircraft_statutory_certificate_schema.AircraftStatutoryCertificateCreate(**parsed)
        return await create_aircraft_statutory_certificate(session, payload, upload_file)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create certificate: {str(e)}")


@router.put(
    "/{cert_id}",
    response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead,
)
async def api_update(
    cert_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update an aircraft statutory certificate. Send JSON as 'json_data' and optional file as 'upload_file'."""
    try:
        parsed = json.loads(json_data)
        payload = aircraft_statutory_certificate_schema.AircraftStatutoryCertificateUpdate(**parsed)
        updated = await update_aircraft_statutory_certificate(
            session=session,
            cert_id=cert_id,
            data=payload,
            upload_file=upload_file,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
        return updated
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update certificate: {str(e)}")


@router.delete("/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    cert_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an aircraft statutory certificate."""
    deleted = await soft_delete_aircraft_statutory_certificate(session, cert_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return None


# ---------- Aircraft-scoped routes ----------
@router_aircraft_scoped.get("/{aircraft_id}/aircraft-statutory-certificates/paged")
async def api_list_by_aircraft_paged(
    aircraft_id: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    category_type: Optional[CategoryTypeEnum] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """List statutory certificates for a specific aircraft with pagination and optional category_type filter."""
    offset = (page - 1) * limit
    items, total = await list_aircraft_statutory_certificates(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_id,
        category_type=category_type,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.get(
    "/{aircraft_id}/aircraft-statutory-certificates/{cert_id}",
    response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead,
)
async def api_get_by_aircraft(
    aircraft_id: int,
    cert_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single certificate by ID scoped to aircraft."""
    obj = await get_aircraft_statutory_certificate_by_aircraft(session, cert_id, aircraft_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead.from_orm(obj)


@router_aircraft_scoped.post(
    "/{aircraft_id}/aircraft-statutory-certificates/",
    response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_by_aircraft(
    aircraft_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Create a certificate for a specific aircraft (aircraft_fk is set from path)."""
    try:
        parsed = json.loads(json_data)
        parsed["aircraft_fk"] = aircraft_id
        payload = aircraft_statutory_certificate_schema.AircraftStatutoryCertificateCreate(**parsed)
        return await create_aircraft_statutory_certificate(session, payload, upload_file)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create certificate: {str(e)}")


@router_aircraft_scoped.put(
    "/{aircraft_id}/aircraft-statutory-certificates/{cert_id}",
    response_model=aircraft_statutory_certificate_schema.AircraftStatutoryCertificateRead,
)
async def api_update_by_aircraft(
    aircraft_id: int,
    cert_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update a certificate scoped to aircraft."""
    existing = await get_aircraft_statutory_certificate_by_aircraft(session, cert_id, aircraft_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    try:
        parsed = json.loads(json_data)
        payload = aircraft_statutory_certificate_schema.AircraftStatutoryCertificateUpdate(**parsed)
        updated = await update_aircraft_statutory_certificate(
            session=session,
            cert_id=cert_id,
            data=payload,
            upload_file=upload_file,
        )
        return updated
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update certificate: {str(e)}")


@router_aircraft_scoped.delete(
    "/{aircraft_id}/aircraft-statutory-certificates/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def api_delete_by_aircraft(
    aircraft_id: int,
    cert_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a certificate scoped to aircraft."""
    existing = await get_aircraft_statutory_certificate_by_aircraft(session, cert_id, aircraft_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    await soft_delete_aircraft_statutory_certificate(session, cert_id)
    return None
