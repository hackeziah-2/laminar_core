from math import ceil
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.organizational_approval_schema import (
    OrganizationalApprovalCreate,
    OrganizationalApprovalUpdate,
    OrganizationalApprovalRead,
    OrganizationalApprovalCreateRequestBody,
    OrganizationalApprovalUpdateRequestBody,
)
from app.repository.organizational_approval import (
    list_organizational_approvals,
    get_organizational_approval,
    create_organizational_approval,
    update_organizational_approval,
    soft_delete_organizational_approval,
)
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation

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
        description="Sort: certificate_category_types__name, certification, date_of_expiration, -date_of_expiration, created_at, etc.",
    ),
    sort_by: Optional[str] = Query(
        None,
        description="Sort column when not using sort. E.g. date_of_expiration, id, certification.",
    ),
    order: Literal["asc", "desc"] = Query(
        "asc",
        description="Direction for sort_by (ignored when sort is non-empty).",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List organizational approvals with pagination. Sort by certificate_category_types__name (category name), date_of_expiration; search on number and web_link."""
    offset = (page - 1) * limit
    effective_sort = (sort or "").strip()
    if not effective_sort and sort_by and sort_by.strip():
        col = sort_by.strip()
        effective_sort = f"-{col}" if order == "desc" else col
    items, total = await list_organizational_approvals(
        session=session,
        limit=limit,
        offset=offset,
        certificate_fk=certificate_fk,
        search=search,
        sort=effective_sort,
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
    body: OrganizationalApprovalCreateRequestBody,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create an organizational approval. Send JSON body: { \"json_data\": { certificate_fk, number?, date_of_expiration?, web_link? } }."""
    try:
        return await create_organizational_approval(
            session,
            body.json_data,
            audit_account_id=current_account.id,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create: {str(e)}")


async def _api_update_impl(
    approval_id: int,
    body: OrganizationalApprovalUpdateRequestBody,
    session: AsyncSession,
    audit_account_id: int,
):
    """Shared update logic for PUT and PATCH."""
    try:
        updated = await update_organizational_approval(
            session=session,
            approval_id=approval_id,
            data=body.json_data,
            audit_account_id=audit_account_id,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational approval not found")
        return updated
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors() if hasattr(e, "errors") else str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update: {str(e)}")


@router.put("/{approval_id}", response_model=OrganizationalApprovalRead)
async def api_update(
    approval_id: int,
    body: OrganizationalApprovalUpdateRequestBody,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update an organizational approval. Send JSON body: { \"json_data\": { certificate_fk?, number?, date_of_expiration?, web_link? } }."""
    return await _api_update_impl(
        approval_id, body, session, current_account.id
    )


@router.patch("/{approval_id}", response_model=OrganizationalApprovalRead)
async def api_patch(
    approval_id: int,
    body: OrganizationalApprovalUpdateRequestBody,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update an organizational approval (partial). Send JSON body: { \"json_data\": { ... } }."""
    return await _api_update_impl(
        approval_id, body, session, current_account.id
    )


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
