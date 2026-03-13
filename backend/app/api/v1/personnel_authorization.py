from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.personnel_authorization_schema import (
    PersonnelAuthorizationCreate,
    PersonnelAuthorizationUpdate,
    PersonnelAuthorizationRead,
)
from app.repository.personnel_authorization import (
    list_personnel_authorizations,
    get_personnel_authorization,
    create_personnel_authorization,
    update_personnel_authorization,
    soft_delete_personnel_authorization,
)
from app.database import get_session

router = APIRouter(
    prefix="/api/v1/personnel-authorization",
    tags=["personnel-authorization"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(
        None,
        description="Search by account_information name (first_name, last_name)",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort: date_of_expiration, -date_of_expiration, auth_expiry_date, -auth_expiry_date, etc.",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List personnel authorizations with pagination. Sort ASC/DESC by date_of_expiration (auth_expiry_date); search by account name."""
    offset = (page - 1) * limit
    items, total = await list_personnel_authorizations(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [PersonnelAuthorizationRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{auth_id}", response_model=PersonnelAuthorizationRead)
async def api_get(
    auth_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single Personnel Authorization by ID."""
    obj = await get_personnel_authorization(session, auth_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel authorization not found",
        )
    return PersonnelAuthorizationRead.from_orm(obj)


@router.post(
    "/",
    response_model=PersonnelAuthorizationRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    payload: PersonnelAuthorizationCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new Personnel Authorization."""
    return await create_personnel_authorization(session, payload)


@router.put("/{auth_id}", response_model=PersonnelAuthorizationRead)
async def api_update(
    auth_id: int,
    payload: PersonnelAuthorizationUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a Personnel Authorization."""
    updated = await update_personnel_authorization(session, auth_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel authorization not found",
        )
    return updated


@router.delete("/{auth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    auth_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a Personnel Authorization."""
    deleted = await soft_delete_personnel_authorization(session, auth_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel authorization not found",
        )
    return None
