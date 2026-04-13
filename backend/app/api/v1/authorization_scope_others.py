from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.authorization_scope_others_schema import (
    AuthorizationScopeOthersCreate,
    AuthorizationScopeOthersUpdate,
    AuthorizationScopeOthersRead,
    AuthorizationScopeOthersListItem,
)
from app.repository.authorization_scope_others import (
    list_authorization_scope_others,
    get_authorization_scope_others,
    create_authorization_scope_others,
    update_authorization_scope_others,
    soft_delete_authorization_scope_others,
    get_all_authorization_scope_others_list,
)
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation

router = APIRouter(
    prefix="/api/v1/authorization-scope-others",
    tags=["authorization-scope-others"],
)


@router.get("/list", response_model=List[AuthorizationScopeOthersListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    """Get all Authorization Scope (Others) for dropdowns (no pagination)."""
    items = await get_all_authorization_scope_others_list(session)
    return [AuthorizationScopeOthersListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of Authorization Scope (Others)."""
    offset = (page - 1) * limit
    items, total = await list_authorization_scope_others(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AuthorizationScopeOthersRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{scope_id}", response_model=AuthorizationScopeOthersRead)
async def api_get(
    scope_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single Authorization Scope (Others) by ID."""
    obj = await get_authorization_scope_others(session, scope_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope (others) not found",
        )
    return obj


@router.post(
    "/",
    response_model=AuthorizationScopeOthersRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: AuthorizationScopeOthersCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new Authorization Scope (Others)."""
    return await create_authorization_scope_others(
        session, payload, audit_account_id=current_account.id
    )


@router.put("/{scope_id}", response_model=AuthorizationScopeOthersRead)
async def api_update(
    scope_id: int,
    payload: AuthorizationScopeOthersUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update an Authorization Scope (Others)."""
    updated = await update_authorization_scope_others(
        session,
        scope_id,
        payload,
        audit_account_id=current_account.id,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope (others) not found",
        )
    return updated


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    scope_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete an Authorization Scope (Others)."""
    deleted = await soft_delete_authorization_scope_others(session, scope_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope (others) not found",
        )
    return None
