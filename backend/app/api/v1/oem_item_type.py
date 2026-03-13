from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.oem_item_type_schema import (
    OemItemTypeCreate,
    OemItemTypeUpdate,
    OemItemTypeRead,
    OemItemTypeListItem,
)
from app.repository.oem_item_type import (
    list_oem_item_types,
    get_oem_item_type,
    create_oem_item_type,
    update_oem_item_type,
    soft_delete_oem_item_type,
    get_all_oem_item_types_list,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/oem-item-types",
    tags=["oem-item-types"],
)


@router.get("/list", response_model=List[OemItemTypeListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    """Get all OEM item types for dropdowns (no pagination)."""
    items = await get_all_oem_item_types_list(session)
    return [OemItemTypeListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of OEM item types."""
    offset = (page - 1) * limit
    items, total = await list_oem_item_types(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [OemItemTypeRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{item_type_id}", response_model=OemItemTypeRead)
async def api_get(
    item_type_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single OEM item type by ID."""
    obj = await get_oem_item_type(session, item_type_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM item type not found")
    return obj


@router.post(
    "/",
    response_model=OemItemTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: OemItemTypeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new OEM item type."""
    return await create_oem_item_type(session, payload)


@router.put("/{item_type_id}", response_model=OemItemTypeRead)
async def api_update(
    item_type_id: int,
    payload: OemItemTypeUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an OEM item type."""
    updated = await update_oem_item_type(session, item_type_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM item type not found")
    return updated


@router.delete("/{item_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    item_type_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an OEM item type."""
    deleted = await soft_delete_oem_item_type(session, item_type_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OEM item type not found")
    return None
