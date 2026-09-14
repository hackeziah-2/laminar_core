from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.module_schema import (
    ModuleCreate,
    ModuleUpdate,
    ModuleRead,
    ModuleListItem
)
from app.repository.module import (
    list_modules,
    get_module,
    create_module,
    update_module,
    soft_delete_module,
    get_all_modules_list,
)
from app.api.deps import get_current_active_account
from app.api.pagination import Pagination, paged_payload, pagination_params
from app.database import get_session
from app.models.account import AccountInformation

router = APIRouter(
    prefix="/api/v1/modules",
    tags=["modules"]
)

@router.get("/module-list", response_model=List[ModuleListItem])
@router.get("/modules-list", response_model=List[ModuleListItem])
async def api_modules_list(session: AsyncSession = Depends(get_session)):
    """Get all Modules for dropdowns (no pagination)."""
    items = await get_all_modules_list(session)
    return [ModuleListItem.from_orm(m) for m in items]


@router.get("/paged")
async def api_list_paged(
    pagination: Pagination = Depends(pagination_params),
    search: Optional[str] = None,
    sort: Optional[str] = Query(
        "",
        description="Example: -created_at,name"
    ),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Modules."""
    items, total = await list_modules(
        session=session,
        limit=pagination.limit,
        offset=pagination.offset,
        search=search,
        sort=sort,
    )
    items_schemas = [ModuleRead.from_orm(item) for item in items]
    return paged_payload(
        items_schemas,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


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
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new Module."""
    return await create_module(
        session,
        payload,
        audit_account_id=current_account.id
    )


@router.put("/{module_id}", response_model=ModuleRead)
async def api_update(
    module_id: int,
    module_in: ModuleUpdate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update a Module."""
    updated = await update_module(
        session=session,
        module_id=module_id,
        module_in=module_in,
        audit_account_id=current_account.id,
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
