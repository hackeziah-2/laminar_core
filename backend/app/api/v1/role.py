from math import ceil
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
    RoleReadWithPermissions,
    RoleListItem,
    RolePermissionItem,
)
from app.repository.role import (
    list_roles,
    get_role,
    get_role_with_permissions,
    create_role,
    update_role,
    soft_delete_role,
    get_all_roles_list,
)
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation

router = APIRouter(
    prefix="/api/v1/roles",
    tags=["roles"]
)


@router.get("/roles-list", response_model=List[RoleListItem])
async def api_roles_list(session: AsyncSession = Depends(get_session)):
    """Get all Roles for dropdowns (no pagination), with user count per role."""
    items = await get_all_roles_list(session)
    return [
        RoleListItem(id=r.id, name=r.name, user_count=user_count)
        for r, user_count in items
    ]


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort: Optional[str] = Query(
        "",
        description="Example: -created_at,name"
    ),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Roles."""
    offset = (page - 1) * limit
    items, total = await list_roles(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [RoleRead.from_orm(item) for item in items]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


def _role_permissions_list(role) -> List[RolePermissionItem]:
    """Build permissions list from role.permissions (only non-deleted)."""
    items = []
    for rp in getattr(role, "permissions", []) or []:
        if getattr(rp, "is_deleted", False):
            continue
        module = getattr(rp, "module", None)
        if not module or getattr(module, "is_deleted", False):
            continue
        items.append(
            RolePermissionItem(
                module=module.name,
                read=getattr(rp, "can_read", False),
                write=getattr(rp, "can_write", False),
                approve=getattr(rp, "can_approve", False),
            )
        )
    return items


@router.get("/{role_id}/permissions", response_model=List[RolePermissionItem])
async def api_get_role_permissions(
    role_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get permissions array for a role (module, read, write, approve)."""
    role = await get_role_with_permissions(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return _role_permissions_list(role)


@router.get("/{role_id}", response_model=RoleReadWithPermissions)
async def api_get(
    role_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Role by ID, including permissions per module."""
    role = await get_role_with_permissions(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    base = RoleRead.from_orm(role)
    return RoleReadWithPermissions(
        **base.dict(),
        permissions=_role_permissions_list(role),
    )


@router.post(
    "/",
    response_model=RoleReadWithPermissions,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: RoleCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new Role. Optionally include permissions (module, read, write, approve) per module."""
    role = await create_role(
        session, payload, audit_account_id=current_account.id
    )
    role_with_perms = await get_role_with_permissions(session, role.id)
    base = RoleRead.from_orm(role_with_perms)
    return RoleReadWithPermissions(
        **base.dict(),
        permissions=_role_permissions_list(role_with_perms),
    )


@router.put("/{role_id}", response_model=RoleReadWithPermissions)
async def api_update(
    role_id: int,
    role_in: RoleUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update a Role. Optionally include permissions to replace existing ones."""
    updated = await update_role(
        session=session,
        role_id=role_id,
        role_in=role_in,
        audit_account_id=current_account.id,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    role_with_perms = await get_role_with_permissions(session, role_id)
    base = RoleRead.from_orm(role_with_perms)
    return RoleReadWithPermissions(
        **base.dict(),
        permissions=_role_permissions_list(role_with_perms),
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    role_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a Role."""
    deleted = await soft_delete_role(session, role_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return None
