import json
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status, Form, File, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.organizational_approval_schema import (
    OrganizationalApprovalCreate,
    OrganizationalApprovalUpdate,
    OrganizationalApprovalRead,
)
from app.repository.organizational_approval import (
    list_organizational_approvals,
    get_organizational_approval,
    create_organizational_approval,
    update_organizational_approval,
    soft_delete_organizational_approval,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/organizational-approvals",
    tags=["organizational-approvals"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    certificate_fk: Optional[int] = Query(None, description="Filter by certificate category type ID"),
    search: Optional[str] = Query(None, description="Search in number, web_link"),
    sort: Optional[str] = Query(
        "",
        description="Sort: certification, date_of_expiration, -date_of_expiration, created_at, etc.",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List organizational approvals with pagination. Sort ASC/DESC by certification (category name), date_of_expiration; search on number and web_link."""
    offset = (page - 1) * limit
    items, total = await list_organizational_approvals(
        session=session,
        limit=limit,
        offset=offset,
        certificate_fk=certificate_fk,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [OrganizationalApprovalRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{approval_id}", response_model=OrganizationalApprovalRead)
async def api_get(
    approval_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single organizational approval by ID."""
    obj = await get_organizational_approval(session, approval_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational approval not found")
    return OrganizationalApprovalRead.from_orm(obj)


@router.post(
    "/",
    response_model=OrganizationalApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Create an organizational approval. Send JSON as 'json_data' and optional file as 'upload_file'."""
    try:
        parsed = json.loads(json_data)
        payload = OrganizationalApprovalCreate(**parsed)
        return await create_organizational_approval(session, payload, upload_file)
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
        raise HTTPException(status_code=400, detail=f"Failed to create: {str(e)}")


@router.put("/{approval_id}", response_model=OrganizationalApprovalRead)
async def api_update(
    approval_id: int,
    json_data: str = Form(...),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Update an organizational approval. Send JSON as 'json_data' and optional file as 'upload_file'."""
    try:
        parsed = json.loads(json_data)
        payload = OrganizationalApprovalUpdate(**parsed)
        updated = await update_organizational_approval(
            session=session,
            approval_id=approval_id,
            data=payload,
            upload_file=upload_file,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational approval not found")
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
        raise HTTPException(status_code=400, detail=f"Failed to update: {str(e)}")


@router.delete("/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    approval_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an organizational approval."""
    deleted = await soft_delete_organizational_approval(session, approval_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational approval not found")
    return None
