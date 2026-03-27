from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.organizational_approval_history import (
    list_organizational_approvals_history,
    get_organizational_approval_history,
    create_organizational_approval_history,
)
from app.schemas.organizational_approval_history_schema import (
    OrganizationalApprovalHistoryCreate,
    OrganizationalApprovalHistoryRead,
)

router = APIRouter(
    prefix="/api/v1/organizational-approvals-history",
    tags=["organizational-approvals-history"],
)


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    certificate_fk: Optional[int] = Query(None),
    oa_history: Optional[int] = Query(
        None,
        description="Filter by organizational_approvals.id (FK)",
    ),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_organizational_approvals_history(
        session=session,
        limit=limit,
        offset=offset,
        certificate_fk=certificate_fk,
        oa_history=oa_history,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [OrganizationalApprovalHistoryRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{oa_history}/paged")
async def api_list_paged_by_oa_history(
    oa_history: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_organizational_approvals_history(
        session=session,
        limit=limit,
        offset=offset,
        oa_history=oa_history,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [OrganizationalApprovalHistoryRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{history_id}", response_model=OrganizationalApprovalHistoryRead)
async def api_get(
    history_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_organizational_approval_history(session, history_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History record not found")
    return OrganizationalApprovalHistoryRead.from_orm(obj)


@router.post(
    "/",
    response_model=OrganizationalApprovalHistoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create(
    body: OrganizationalApprovalHistoryCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_organizational_approval_history(session, body)
