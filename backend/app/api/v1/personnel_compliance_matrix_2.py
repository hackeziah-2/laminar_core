import json
import time
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.database import get_session
from app.models.account import AccountInformation
from app.models.personnel_compliance import PERSONNEL_COMPLIANCE_MODULE_NAME
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
    "",
    response_model=PersonnelComplianceMatrix2PagedResponse,
    summary="Personnel compliance matrix (grouped by account)",
)
@router.get(
    "/",
    response_model=PersonnelComplianceMatrix2PagedResponse,
    summary="Personnel compliance matrix (grouped by account)",
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
    _: AccountInformation = Depends(
        require_permission(PERSONNEL_COMPLIANCE_MODULE_NAME, "can_read")
    ),
):
    offset = (page - 1) * limit
    # region agent log
    try:
        with open(
            "/Users/kevinpaullamadrid/Desktop/Project/laminar_core/.cursor/debug-004053.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(
                json.dumps(
                    {
                        "sessionId": "004053",
                        "timestamp": int(time.time() * 1000),
                        "hypothesisId": "H3-H4",
                        "location": "personnel_compliance_matrix_2.py:api_matrix_2_paged:entry",
                        "message": "request query params",
                        "data": {
                            "limit": limit,
                            "page": page,
                            "offset": offset,
                            "search": (search or "")[:120] if search else None,
                            "sort": (sort or "")[:120] if sort else None,
                            "designation": (account_information__designation or "")[:120]
                            if account_information__designation
                            else None,
                        },
                        "runId": "post-fix",
                    },
                    default=str,
                )
                + "\n"
            )
    except Exception:
        pass
    # endregion
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
            PersonnelComplianceMatrix2Item.from_account_and_personnel_authorization(
                acc,
                pa,
                compliance_by_type=compliance_by_account.get(acc.id),
            )
            for acc, pa in rows
        ],
        total=total,
        page=page,
        pages=pages,
    )
