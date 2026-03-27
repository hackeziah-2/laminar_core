from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.personnel_compliance_matrix_2 import (
    list_personnel_compliance_matrix_2_paged,
)
from app.schemas.personnel_compliance_matrix_2_schema import (
    PersonnelComplianceMatrix2Item,
    PersonnelComplianceMatrix2PagedResponse,
)

router = APIRouter(
    prefix="/api/v1/personnel-compliance-matrix-2",
    tags=["personnel-compliance-matrix-2"],
)


@router.get(
    "/paged",
    response_model=PersonnelComplianceMatrix2PagedResponse,
    summary="Personnel compliance matrix (grouped by account)",
)
async def api_matrix_2_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(
        None,
        description="Search by account name (first, last, middle, or Last, First / First Last patterns).",
    ),
    sort: Optional[str] = Query(
        "",
        description=(
            "Sort keys: name, full_name, authorization_no, account_information_id, "
            "auth_expiry_date, caap_lic_expiry, hf_training_expiry, "
            "type_training_expiry_cessna, type_training_expiry_baron, etc. Prefix with - for DESC."
        ),
    ),
    account_information__designation: Optional[str] = Query(
        None,
        description="Filter by account designation (position).",
    ),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    rows, total, compliance_by_account = await list_personnel_compliance_matrix_2_paged(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        sort=sort or "",
        designation=account_information__designation,
    )
    pages = ceil(total / limit) if total else 0
    return PersonnelComplianceMatrix2PagedResponse(
        items=[
            PersonnelComplianceMatrix2Item.from_personnel_authorization(
                r,
                compliance_by_type=compliance_by_account.get(r.account_information_id),
            )
            for r in rows
        ],
        total=total,
        page=page,
        pages=pages,
    )
