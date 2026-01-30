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

from app.schemas import account_schema
from app.schemas.account_schema import AccountInformationRead, AccountInformationListItem
from app.repository.account import (
    list_account_informations,
    get_account_information,
    create_account_information,
    update_account_information,
    soft_delete_account_information,
    get_all_account_informations_list
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/account-information",
    tags=["account-information"]
)


@router.get("/account-informations-list", response_model=List[AccountInformationListItem])
async def api_account_informations_list(
    designation: Optional[List[str]] = Query(None, description="Filter by designation(s) - can provide multiple values (case-insensitive partial match). Example: ?designation=pilot&designation=Maintenance+Engineer"),
    search: Optional[str] = Query(None, description="Search across first name, last name, middle name, license number, and username"),
    session: AsyncSession = Depends(get_session)
):
    """Get all Account Information entries with fullname and license_no.
    
    Optionally filter by designation(s) and/or search across name fields and license number.
    Multiple designations can be provided: ?designation=pilot&designation=Maintenance+Engineer
    """
    items = await get_all_account_informations_list(
        session, 
        designation=designation,
        search=search
    )
    
    # Convert to list items with fullname using the schema method
    result = [AccountInformationListItem.from_orm_with_fullname(item) for item in items]
    
    return result


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort: Optional[str] = Query(
        "",
        description="Example: -created_at,username"
    ),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of Account Information entries."""
    offset = (page - 1) * limit
    items, total = await list_account_informations(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    # Convert SQLAlchemy models to Pydantic schemas
    items_schemas = [AccountInformationRead.from_orm(item) for item in items]
    return {
        "items": items_schemas,
        "total": total,
        "page": page,
        "pages": pages
    }


@router.get(
    "/{account_id}",
    response_model=account_schema.AccountInformationRead
)
async def api_get(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single Account Information entry by ID."""
    obj = await get_account_information(session, account_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Account Information not found"
        )
    return obj


@router.post(
    "/",
    response_model=account_schema.AccountInformationRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: account_schema.AccountInformationCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new Account Information entry."""
    return await create_account_information(session, payload)


@router.put(
    "/{account_id}",
    response_model=account_schema.AccountInformationRead
)
async def api_update(
    account_id: int,
    account_in: account_schema.AccountInformationUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an Account Information entry."""
    updated = await update_account_information(
        session=session,
        account_id=account_id,
        account_in=account_in,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Account Information not found"
        )

    return updated


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def api_delete(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Account Information entry."""
    deleted = await soft_delete_account_information(session, account_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account Information not found",
        )
    # 204 No Content should not return a body
    return None
