from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.audit import (
    AUTHORIZATION_SCOPE_PIPER_PA34_MODULE_NAME,
    AUTHORIZATION_SCOPE_PIPER_PA34_TABLE_NAME,
)
from app.schemas.authorization_scope_piper_pa34_schema import (
    AuthorizationScopePiperPa34Create,
    AuthorizationScopePiperPa34Update,
    AuthorizationScopePiperPa34Read,
    AuthorizationScopePiperPa34ListItem,
)
from app.repository.authorization_scope_piper_pa34 import (
    list_authorization_scope_piper_pa34,
    get_authorization_scope_piper_pa34,
    create_authorization_scope_piper_pa34,
    update_authorization_scope_piper_pa34,
    soft_delete_authorization_scope_piper_pa34,
    get_all_authorization_scope_piper_pa34_list,
)
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation

router = APIRouter(
    prefix="/api/v1/authorization-scope-piper-pa34",
    tags=["authorization-scope-piper-pa34"],
)


@router.get("/list", response_model=List[AuthorizationScopePiperPa34ListItem])
async def api_list_all(session: AsyncSession = Depends(get_session)):
    """Get all Authorization Scope Piper PA-34 for dropdowns (no pagination)."""
    items = await get_all_authorization_scope_piper_pa34_list(session)
    return [AuthorizationScopePiperPa34ListItem.from_orm(i) for i in items]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("", description="Example: -created_at,name"),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of Authorization Scope Piper PA-34."""
    offset = (page - 1) * limit
    items, total = await list_authorization_scope_piper_pa34(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [AuthorizationScopePiperPa34Read.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{scope_id}", response_model=AuthorizationScopePiperPa34Read)
async def api_get(
    scope_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single Authorization Scope Piper PA-34 by ID."""
    obj = await get_authorization_scope_piper_pa34(session, scope_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Piper PA-34 not found",
        )
    return obj


@router.post(
    "/",
    response_model=AuthorizationScopePiperPa34Read,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    request: Request,
    payload: AuthorizationScopePiperPa34Create,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new Authorization Scope Piper PA-34."""
    return await create_authorization_scope_piper_pa34(
        session,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=AUTHORIZATION_SCOPE_PIPER_PA34_MODULE_NAME,
        audit_table_name=AUTHORIZATION_SCOPE_PIPER_PA34_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )


@router.put("/{scope_id}", response_model=AuthorizationScopePiperPa34Read)
async def api_update(
    scope_id: int,
    request: Request,
    payload: AuthorizationScopePiperPa34Update,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update an Authorization Scope Piper PA-34."""
    updated = await update_authorization_scope_piper_pa34(
        session,
        scope_id,
        payload,
        audit_account_id=current_account.id,
        audit_module_name=AUTHORIZATION_SCOPE_PIPER_PA34_MODULE_NAME,
        audit_table_name=AUTHORIZATION_SCOPE_PIPER_PA34_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Piper PA-34 not found",
        )
    return updated


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    scope_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Soft delete an Authorization Scope Piper PA-34."""
    deleted = await soft_delete_authorization_scope_piper_pa34(
        session,
        scope_id,
        audit_module_name=AUTHORIZATION_SCOPE_PIPER_PA34_MODULE_NAME,
        audit_table_name=AUTHORIZATION_SCOPE_PIPER_PA34_TABLE_NAME,
        audit_user=current_account,
        audit_request=request,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization scope Piper PA-34 not found",
        )
    return None
