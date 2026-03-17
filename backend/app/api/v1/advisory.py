from math import ceil
from typing import Optional, Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.advisory import (
    list_advisory_items,
    list_advisory_items_grouped,
    list_advisory_items_grouped_by_type,
)
from app.schemas.advisory_schema import (
    AdvisoryFilterOption,
    AdvisoryFilterOptionsResponse,
    AdvisoryGroupedByTypePagedResponse,
    AdvisoryGroupedPagedResponse,
    AdvisoryPagedResponse,
)

router = APIRouter(
    prefix="/api/v1/advisory",
    tags=["advisory"],
)

# Same API at /advisory (no /api/v1) for convenience
router_advisory = APIRouter(prefix="/advisory", tags=["advisory"])

# Filter options for type dropdown (value + label)
ADVISORY_TYPE_FILTER_OPTIONS = [
    AdvisoryFilterOption(value="CERTIFICATE", label="CERTIFICATE"),
    AdvisoryFilterOption(value="SUBSCRIPTION", label="SUBSCRIPTION"),
    AdvisoryFilterOption(value="REGULATORY_CORRESPONDENCE_NON_CERT", label="REGULATORY CORRESPONDENCE NON CERT"),
    AdvisoryFilterOption(value="LICENSE", label="LICENSE"),
]


@router.get(
    "/filter-options",
    response_model=AdvisoryFilterOptionsResponse,
    summary="Advisory type filter options",
)
async def get_advisory_filter_options():
    """
    Returns the list of type filter options (value, label) for building a filter dropdown.
    Use `value` as the query param `?type=...` when calling GET /advisory.
    """
    return AdvisoryFilterOptionsResponse(filters=ADVISORY_TYPE_FILTER_OPTIONS)


@router.get(
    "",
    response_model=Union[
        AdvisoryPagedResponse,
        AdvisoryGroupedPagedResponse,
        AdvisoryGroupedByTypePagedResponse,
    ],
)
@router.get(
    "/",
    response_model=Union[
        AdvisoryPagedResponse,
        AdvisoryGroupedPagedResponse,
        AdvisoryGroupedByTypePagedResponse,
    ],
)
async def get_advisory_paged(
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    page: int = Query(1, ge=1, description="Page number"),
    sort_expiry: str = Query(
        "asc",
        description="Sort by expiry: 'asc' (earliest first) or 'desc' (latest first)",
    ),
    type_filter: Optional[str] = Query(
        None,
        alias="type",
        description="FILTER by Type: CERTIFICATE | REGULATORY_CORRESPONDENCE_NON_CERT | LICENSE | SUBSCRIPTION. Use GET /advisory/filter-options for value/label list.",
    ),
    group_by: Optional[str] = Query(
        None,
        description="Group by 'type', 'item,type', or 'item and type': type = groups by type; item,type = groups by item and type with expiries per group",
    ),
    session: AsyncSession = Depends(get_session),
):
    """
    **Advisory API (paginated).** Returns items with ITEM, TYPE, EXPIRY, REMAINING VALIDITY.

    **ITEM** from:
    - REGISTRATION (Aircraft Statutory Certificates)
    - CERTIFICATE name (Organizational Approvals)
    - Item Type name (OEM Technical Publication)
    - NAME (Personnel Authorization)

    **TYPE** from:
    - Aircraft Statutory Certificates: REGULATORY_CORRESPONDENCE_NON_CERT if Certificate Type is MARKING RESERVATION EXPIRY or BINARY CODE 24BIT, else CERTIFICATE
    - Organizational Approvals: CERTIFICATE
    - OEM Technical Publication: category_type; if SUBSCRIPTION then SUBSCRIPTION
    - Personnel Authorization: LICENSE for CAAP LIC EXPIRY, else CERTIFICATE

    **EXPIRY**: date_of_expiration  
    **REMAINING VALIDITY**: (today - date_of_expiration).days (negative = days left, positive = overdue)

    **Pagination**: `page`, `limit` (page size); response includes `items`, `total`, `page`, `pages`.

    **FILTER by Type**: query param `type` = CERTIFICATE | REGULATORY_CORRESPONDENCE_NON_CERT | LICENSE | SUBSCRIPTION. See GET /advisory/filter-options for value/label list.

    **Group by**: `group_by=type` or `group_by=item,type` for grouped views (paginated by group).
    """
    offset = (page - 1) * limit
    sort_expiry_asc = sort_expiry.strip().lower() != "desc"
    group_by_val = (group_by or "").strip().lower().replace(" and ", ",")

    if group_by_val == "type":
        type_groups, total = await list_advisory_items_grouped_by_type(
            session=session,
            limit=limit,
            offset=offset,
            sort_expiry_asc=sort_expiry_asc,
            type_filter=type_filter,
        )
        pages = ceil(total / limit) if total else 0
        return AdvisoryGroupedByTypePagedResponse(
            type_groups=type_groups,
            total=total,
            page=page,
            pages=pages,
        )

    if group_by_val == "item,type":
        groups, total = await list_advisory_items_grouped(
            session=session,
            limit=limit,
            offset=offset,
            sort_expiry_asc=sort_expiry_asc,
            type_filter=type_filter,
        )
        pages = ceil(total / limit) if total else 0
        return AdvisoryGroupedPagedResponse(
            groups=groups,
            total=total,
            page=page,
            pages=pages,
        )

    items, total = await list_advisory_items(
        session=session,
        limit=limit,
        offset=offset,
        sort_expiry_asc=sort_expiry_asc,
        type_filter=type_filter,
    )
    pages = ceil(total / limit) if total else 0
    return AdvisoryPagedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


# Expose same endpoints at GET /advisory and GET /api/v1/advisory
router_advisory.get("/filter-options", response_model=AdvisoryFilterOptionsResponse)(get_advisory_filter_options)
router_advisory.get(
    "",
    response_model=Union[
        AdvisoryPagedResponse,
        AdvisoryGroupedPagedResponse,
        AdvisoryGroupedByTypePagedResponse,
    ],
)(get_advisory_paged)
router_advisory.get(
    "/",
    response_model=Union[
        AdvisoryPagedResponse,
        AdvisoryGroupedPagedResponse,
        AdvisoryGroupedByTypePagedResponse,
    ],
)(get_advisory_paged)
