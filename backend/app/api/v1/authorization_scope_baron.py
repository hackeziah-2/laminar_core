from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.authorization_scope_baron_schema import (
    AuthorizationScopeBaronCreate,
    AuthorizationScopeBaronUpdate,
    AuthorizationScopeBaronRead,
    AuthorizationScopeBaronListItem,
)
from app.repository.authorization_scope_baron import (
    list_authorization_scope_baron,
    get_authorization_scope_baron,
    create_authorization_scope_baron,
    update_authorization_scope_baron,
    soft_delete_authorization_scope_baron,
    get_all_authorization_scope_baron_list,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/authorization-scope-baron",
    tags=["authorization-scope-baron"],
)


@router.get("/list", response_model=List[AuthorizationScopeBaronListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    """Get all Authorization Scope Baron for dropdowns (no pagination)."""
    items = await get_all_authorization_scope_baron_list(session)
    return [AuthorizationScopeBaronListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of Authorization Scope Baron."""
    offset = (page - 1) * limit
    items, total = await list_authorization_scope_baron(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AuthorizationScopeBaronRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{scope_id}", response_model=AuthorizationScopeBaronRead)
async def api_get(
    scope_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single Authorization Scope Baron by ID."""
    obj = await get_authorization_scope_baron(session, scope_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Baron not found",
        )
    return obj


@router.post(
    "/",
    response_model=AuthorizationScopeBaronRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: AuthorizationScopeBaronCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new Authorization Scope Baron."""
    return await create_authorization_scope_baron(session, payload)


@router.put("/{scope_id}", response_model=AuthorizationScopeBaronRead)
async def api_update(
    scope_id: int,
    payload: AuthorizationScopeBaronUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an Authorization Scope Baron."""
    updated = await update_authorization_scope_baron(session, scope_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Baron not found",
        )
    return updated


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    scope_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an Authorization Scope Baron."""
    deleted = await soft_delete_authorization_scope_baron(session, scope_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Baron not found",
        )
    return None
