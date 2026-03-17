from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.oem_technical_publication_schema import (
    OemTechnicalPublicationCreate,
    OemTechnicalPublicationUpdate,
    OemTechnicalPublicationRead,
    OemTechnicalPublicationPagedResponse,
    OemTechnicalPublicationCategoryTypeEnum,
)
from app.repository.oem_technical_publication import (
    list_oem_technical_publications,
    get_oem_technical_publication,
    create_oem_technical_publication,
    update_oem_technical_publication,
    soft_delete_oem_technical_publication,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/oem-technical-publications",
    tags=["oem-technical-publications"],
)


@router.get("/paged", response_model=OemTechnicalPublicationPagedResponse)
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    item_fk: Optional[int] = Query(None, description="Filter by OEM item type ID"),
    category_type: Optional[OemTechnicalPublicationCategoryTypeEnum] = Query(
        None, description="Filter by category type: CERTIFICATE, SUBSCRIPTION, REGULATORY_CORRESPONDENCE_NON_CERT, LICENSE"
    ),
    search: Optional[str] = Query(None, description="Search by item type name"),
    sort: Optional[str] = Query(
        "",
        description="Sort: date_of_expiration, -date_of_expiration, created_at, etc.",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List OEM technical publications with pagination. Sort ASC/DESC by date_of_expiration; search by item type name."""
    offset = (page - 1) * limit
    items, total = await list_oem_technical_publications(
        session=session,
        limit=limit,
        offset=offset,
        item_fk=item_fk,
        category_type=category_type.value if category_type else None,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return OemTechnicalPublicationPagedResponse(
        items=[OemTechnicalPublicationRead.from_orm(i) for i in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{publication_id}", response_model=OemTechnicalPublicationRead)
async def api_get(
    publication_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single OEM technical publication by ID."""
    obj = await get_oem_technical_publication(session, publication_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM technical publication not found")
    return OemTechnicalPublicationRead.from_orm(obj)


@router.post(
    "/",
    response_model=OemTechnicalPublicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: OemTechnicalPublicationCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create an OEM technical publication."""
    return await create_oem_technical_publication(session, payload)


@router.put("/{publication_id}", response_model=OemTechnicalPublicationRead)
async def api_update(
    publication_id: int,
    payload: OemTechnicalPublicationUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an OEM technical publication."""
    updated = await update_oem_technical_publication(session, publication_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM technical publication not found")
    return updated


@router.delete("/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    publication_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an OEM technical publication."""
    deleted = await soft_delete_oem_technical_publication(session, publication_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM technical publication not found")
    return None
