from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.certificate_category_type_schema import (
    CertificateCategoryTypeCreate,
    CertificateCategoryTypeUpdate,
    CertificateCategoryTypeRead,
    CertificateCategoryTypeListItem,
)
from app.repository.certificate_category_type import (
    list_certificate_category_types,
    get_certificate_category_type,
    create_certificate_category_type,
    update_certificate_category_type,
    soft_delete_certificate_category_type,
    get_all_certificate_category_types_list,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/certificate-category-types",
    tags=["certificate-category-types"],
)


@router.get("/list", response_model=List[CertificateCategoryTypeListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    """Get all certificate category types for dropdowns (no pagination)."""
    items = await get_all_certificate_category_types_list(session)
    return [CertificateCategoryTypeListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of certificate category types."""
    offset = (page - 1) * limit
    items, total = await list_certificate_category_types(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [CertificateCategoryTypeRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{category_id}", response_model=CertificateCategoryTypeRead)
async def api_get(
    category_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single certificate category type by ID."""
    obj = await get_certificate_category_type(session, category_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate category type not found")
    return obj


@router.post(
    "/",
    response_model=CertificateCategoryTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: CertificateCategoryTypeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new certificate category type."""
    return await create_certificate_category_type(session, payload)


@router.put("/{category_id}", response_model=CertificateCategoryTypeRead)
async def api_update(
    category_id: int,
    payload: CertificateCategoryTypeUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a certificate category type."""
    updated = await update_certificate_category_type(session, category_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate category type not found")
    return updated


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    category_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a certificate category type."""
    deleted = await soft_delete_certificate_category_type(session, category_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate category type not found")
    return None
