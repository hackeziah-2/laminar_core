from math import ceil
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.database import get_session
from app.models.account import AccountInformation
from app.models.personnel_compliance import (
    PERSONNEL_COMPLIANCE_MODULE_NAME,
    PersonnelComplianceItemType,
)
from app.repository.personnel_compliance import (
    create_personnel_compliance,
    get_personnel_compliance,
    list_personnel_compliances,
    soft_delete_personnel_compliance,
    update_personnel_compliance,
)
from app.schemas.personnel_compliance_schema import (
    PersonnelComplianceCreate,
    PersonnelCompliancePagedResponse,
    PersonnelComplianceRead,
    PersonnelComplianceUpdate,
)

router = APIRouter(
    prefix="/api/v1/personnel-compliance",
    tags=["personnel-compliance"],
)


async def _list_paged(
    session: AsyncSession,
    limit: int = 10,
    page: int = 1,
    search: Optional[str] = None,
    sort: Optional[str] = "",
    account_information__designation: Optional[str] = None,
    item_type: Optional[PersonnelComplianceItemType] = None,
):
    offset = (page - 1) * limit
    items, total = await list_personnel_compliances(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        designation=account_information__designation,
        item_type=item_type,
    )
    pages = ceil(total / limit) if total else 0
    return PersonnelCompliancePagedResponse(
        items=[PersonnelComplianceRead.from_orm(i) for i in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("", response_model=PersonnelCompliancePagedResponse)
@router.get("/", response_model=PersonnelCompliancePagedResponse)
async def api_list(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(
        None,
        description="Search by account name: first_name, last_name, middle_name, or combined patterns (e.g. Last, First or First Last).",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort: full_name, -full_name, expiry_date, -expiry_date, item_type, id, created_at, account_information_id__auth_stamp, etc.",
    ),
    account_information__designation: Optional[str] = Query(
        None,
        description="Filter by account_information designation",
    ),
    item_type: Optional[PersonnelComplianceItemType] = Query(
        None,
        description="Filter by compliance item type",
    ),
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_read")
    ),
):
    return await _list_paged(
        session=session,
        limit=limit,
        page=page,
        search=search,
        sort=sort,
        account_information__designation=account_information__designation,
        item_type=item_type,
    )


@router.get("/paged", response_model=PersonnelCompliancePagedResponse)
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(
        None,
        description="Search by account name: first_name, last_name, middle_name, or combined patterns (e.g. Last, First or First Last).",
    ),
    sort: Optional[str] = Query(
        "",
        description="Sort: full_name, -full_name, expiry_date, -expiry_date, item_type, id, created_at, account_information_id__auth_stamp, etc.",
    ),
    account_information__designation: Optional[str] = Query(
        None,
        description="Filter by account_information designation",
    ),
    item_type: Optional[PersonnelComplianceItemType] = Query(
        None,
        description="Filter by compliance item type",
    ),
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_read")
    ),
):
    return await _list_paged(
        session=session,
        limit=limit,
        page=page,
        search=search,
        sort=sort,
        account_information__designation=account_information__designation,
        item_type=item_type,
    )


@router.post("", response_model=PersonnelComplianceRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PersonnelComplianceRead, status_code=status.HTTP_201_CREATED)
async def api_create(
    payload: PersonnelComplianceCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_create")
    ),
):
    return await create_personnel_compliance(
        session, payload, audit_account_id=current_account.id
    )


@router.get("/{compliance_id}", response_model=PersonnelComplianceRead)
async def api_get(
    compliance_id: int = Path(..., ge=1, description="Personnel compliance ID"),
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_read")
    ),
):
    obj = await get_personnel_compliance(session, compliance_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel compliance not found",
        )
    return PersonnelComplianceRead.from_orm(obj)


@router.put("/{compliance_id}", response_model=PersonnelComplianceRead)
async def api_update(
    compliance_id: int = Path(..., ge=1, description="Personnel compliance ID"),
    payload: PersonnelComplianceUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_update")
    ),
):
    updated = await update_personnel_compliance(
        session,
        compliance_id,
        payload,
        audit_account_id=current_account.id,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel compliance not found",
        )
    return updated


@router.delete("/{compliance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete(
    compliance_id: int = Path(..., ge=1, description="Personnel compliance ID"),
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_delete")
    ),
):
    deleted = await soft_delete_personnel_compliance(session, compliance_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel compliance not found",
        )
    return None
