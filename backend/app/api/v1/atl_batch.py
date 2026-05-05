from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.atl_batch import (
    create_atl_batch,
    get_atl_batch,
    get_all_atl_batches_list,
    list_atl_batches_paged,
    soft_delete_atl_batch,
    update_atl_batch,
)
from app.schemas.atl_batch_schema import (
    AtlBatchCreate,
    AtlBatchListItem,
    AtlBatchRead,
    AtlBatchUpdate,
)

router = APIRouter(
    prefix="/api/v1/atl-batch",
    tags=["atl-batch"],
)


@router.get("/list", response_model=List[AtlBatchListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    items = await get_all_atl_batches_list(session)
    return [AtlBatchListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_atl_batches_paged(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort or "",
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AtlBatchRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{batch_id}", response_model=AtlBatchRead)
async def api_get(batch_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_atl_batch(session, batch_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ATL batch not found")
    return obj


@router.post(
    "/",
    response_model=AtlBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: AtlBatchCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    return await create_atl_batch(session, payload, audit_account_id=current_account.id)


@router.put("/{batch_id}", response_model=AtlBatchRead)
async def api_update(
    batch_id: int,
    payload: AtlBatchUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    updated = await update_atl_batch(
        session, batch_id, payload, audit_account_id=current_account.id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ATL batch not found")
    return updated


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(batch_id: int, session: AsyncSession = Depends(get_session)):
    deleted = await soft_delete_atl_batch(session, batch_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ATL batch not found")
    return None
