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

from app.schemas.module_schema import ModuleCreate, ModuleUpdate, ModuleRead, ModuleListItem
from app.repository.module import (
    list_modules,
    get_module,
    create_module,
    update_module,
    soft_delete_module,
    get_all_modules_list,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/modules",
    tags=["modules"]
)


@router.get("/modules-list", response_model=List[ModuleListItem])
async def api_modules_list(session: AsyncSession = Depends(get_session)):
    """Get all Modules for dropdowns (no pagination)."""
    items = await get_all_modules_list(session)
    return [ModuleListItem.from_orm(m) for m in items]


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
    """Get paginated list of Modules."""
    offset = (page - 1) * limit
    items, total = await list_modules(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    items_schemas = [ModuleRead.from_orm(item) for item in items]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get("/{module_id}", response_model=ModuleRead)
async def api_get(
    module_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Module by ID."""
    obj = await get_module(session, module_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Module not found"
        )
    return obj


@router.post(
    "/",
    response_model=ModuleRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: ModuleCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new Module."""
    return await create_module(session, payload)


@router.put("/{module_id}", response_model=ModuleRead)
async def api_update(
    module_id: int,
    module_in: ModuleUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a Module."""
    updated = await update_module(
        session=session,
        module_id=module_id,
        module_in=module_in,
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Module not found"
        )
    return updated


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    module_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete a Module."""
    deleted = await soft_delete_module(session, module_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return None
