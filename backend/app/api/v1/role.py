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

from app.schemas.role_schema import RoleCreate, RoleUpdate, RoleRead, RoleListItem
from app.repository.role import (
    list_roles,
    get_role,
    create_role,
    update_role,
    soft_delete_role,
    get_all_roles_list,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/roles",
    tags=["roles"]
)


@router.get("/roles-list", response_model=List[RoleListItem])
async def api_roles_list(session: AsyncSession = Depends(get_session)):
    """Get all Roles for dropdowns (no pagination)."""
    items = await get_all_roles_list(session)
    return [RoleListItem.from_orm(r) for r in items]


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


@router.get("/{role_id}", response_model=RoleRead)
async def api_get(
    role_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Role by ID."""
    obj = await get_role(session, role_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )
    return obj


@router.post(
    "/",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: RoleCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new Role."""
    return await create_role(session, payload)


@router.put("/{role_id}", response_model=RoleRead)
async def api_update(
    role_id: int,
    role_in: RoleUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a Role."""
    updated = await update_role(
        session=session,
        role_id=role_id,
        role_in=role_in,
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )
    return updated


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    role_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete a Role."""
    deleted = await soft_delete_role(session, role_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return None
