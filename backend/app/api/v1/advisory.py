from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repository.advisory import (
    get_advisory_detail,
    list_advisory_items,
    update_advisory_expiry,
    update_advisory_withhold,
)
from app.schemas.advisory_schema import (
    AdvisoryDetailResponse,
    AdvisoryFilterOption,
    AdvisoryFilterOptionsResponse,
    AdvisoryPagedResponse,
    AdvisoryUpdateExpiryBody,
    RegulatoryComplianceSource,
)

router = APIRouter(prefix="/api/v1/advisory", tags=["advisory"])
router_advisory = APIRouter(prefix="/advisory", tags=["advisory"])

ADVISORY_TYPE_FILTER_OPTIONS = [
    AdvisoryFilterOption(value="CERTIFICATE", label="CERTIFICATE"),
    AdvisoryFilterOption(value="SUBSCRIPTION", label="SUBSCRIPTION"),
    AdvisoryFilterOption(value="REGULATORY_CORRESPONDENCE_NON_CERT", label="REGULATORY CORRESPONDENCE NON CERT"),
    AdvisoryFilterOption(value="LICENSE", label="LICENSE"),
]


def _parse_sort_remaining_validity(sort: Optional[str]) -> Optional[str]:
    """Return 'asc', 'desc', or None from sort=remaining_validity / -remaining_validity / asc / desc."""
    if not sort or not sort.strip():
        return None
    s = sort.strip().lower()
    if s in ("remaining_validity", "remaining_validity_asc", "asc"):
        return "asc"
    if s in ("-remaining_validity", "remaining_validity_desc", "desc"):
        return "desc"
    return None


async def _fetch_advisory_page(
    *,
    session: AsyncSession,
    page: int,
    limit: int,
    type_filter: Optional[str],
    sort_remaining_validity: Optional[str],
    item_filter: Optional[str],
):
    offset = (page - 1) * limit
    items, total_items = await list_advisory_items(
        session=session,
        limit=limit,
        offset=offset,
        type_filter=type_filter,
        sort_remaining_validity=sort_remaining_validity,
        item_filter=item_filter,
    )
    total_pages = ceil(total_items / limit) if total_items else 0
    return items, total_items, total_pages


@router.get("/filter-options", response_model=AdvisoryFilterOptionsResponse, summary="Advisory type filter options")
async def get_advisory_filter_options():
    return AdvisoryFilterOptionsResponse(filters=ADVISORY_TYPE_FILTER_OPTIONS)


@router.get("", response_model=AdvisoryPagedResponse)
@router.get("/", response_model=AdvisoryPagedResponse)
async def get_advisory(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    type_filter: Optional[str] = Query(
        None,
        alias="type",
        description="Filter by TYPE: CERTIFICATE, SUBSCRIPTION, REGULATORY_CORRESPONDENCE_NON_CERT, or LICENSE",
    ),
    item_filter: Optional[str] = Query(
        None,
        alias="item",
        description="Filter by ITEM: case-insensitive substring match",
    ),
    sort: Optional[str] = Query(
        None,
        description="Sort by REMAINING VALIDITY (integer): asc = lowest first (<=0 then 1..30), desc = highest first (30..1 then <=0). remaining_validity | -remaining_validity",
    ),
    session: AsyncSession = Depends(get_session),
):
    sort_remaining_validity = _parse_sort_remaining_validity(sort)
    items, total_items, total_pages = await _fetch_advisory_page(
        session=session,
        page=page,
        limit=limit,
        type_filter=type_filter,
        sort_remaining_validity=sort_remaining_validity,
        item_filter=item_filter,
    )
    return AdvisoryPagedResponse(
        items=items,
        total=total_items,
        page=page,
        pages=total_pages,
    )


@router.get("/paged", response_model=AdvisoryPagedResponse)
@router.get("/paged/", response_model=AdvisoryPagedResponse)
async def get_advisory_paged(
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    page: int = Query(1, ge=1, description="Page number"),
    type_filter: Optional[str] = Query(
        None,
        alias="type",
        description="Filter by TYPE: CERTIFICATE, SUBSCRIPTION, REGULATORY_CORRESPONDENCE_NON_CERT, or LICENSE",
    ),
    item_filter: Optional[str] = Query(
        None,
        alias="item",
        description="Filter by ITEM: case-insensitive substring match",
    ),
    sort: Optional[str] = Query(
        None,
        description="Sort by REMAINING VALIDITY: asc (lowest first), desc (highest first). remaining_validity | -remaining_validity",
    ),
    session: AsyncSession = Depends(get_session),
):
    return await get_advisory(
        page=page,
        limit=limit,
        type_filter=type_filter,
        item_filter=item_filter,
        sort=sort,
        session=session,
    )


@router.get(
    "/{id}",
    response_model=AdvisoryDetailResponse,
    summary="Get advisory expiry_date and web_link",
)
@router.get(
    "/{id}/",
    response_model=AdvisoryDetailResponse,
    summary="Get advisory expiry_date and web_link",
)
async def get_advisory_by_id(
    id: int,
    regulatory_compliance: RegulatoryComplianceSource = Query(
        ...,
        description="Source table: aircraft-statutory-certificates, organizational-approvals, oem-technical-publication, or personnel-compliance",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Return expiry_date and web_link for the source row (id + regulatory_compliance)."""
    try:
        expiry_date, web_link = await get_advisory_detail(
            session=session,
            regulatory_compliance=regulatory_compliance,
            id=id,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return AdvisoryDetailResponse(expiry_date=expiry_date, web_link=web_link)


@router.put(
    "/{id}/{expiry}/",
    status_code=200,
    summary="Update advisory expiry",
)
async def put_advisory_expiry(
    id: int,
    expiry: str,
    body: AdvisoryUpdateExpiryBody,
    session: AsyncSession = Depends(get_session),
):
    """Update the expiry date for an advisory item by id.

    Body: regulatory_compliance (required); optional web_link (stored on statutory / approval / OEM rows only).

    For aircraft-statutory-certificates, organizational-approvals, oem-technical-publication:
      sets date_of_expiration = expiry and web_link when provided.

    For personnel-compliance: sets expiry_date on the personnel compliance record (web_link ignored).
    """
    try:
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiry date; use YYYY-MM-DD")
    try:
        await update_advisory_expiry(
            session=session,
            regulatory_compliance=body.regulatory_compliance,
            id=id,
            expiry=expiry_date,
            web_link=body.web_link,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "Expiry updated"}


@router.put(
    "/withhold/{id}/{regulatory_compliance}",
    status_code=200,
    summary="Set advisory item to withhold",
)
async def put_advisory_withhold(
    id: int,
    regulatory_compliance: RegulatoryComplianceSource,
    session: AsyncSession = Depends(get_session),
):
    """Set is_withhold to True for an advisory item by id and regulatory_compliance.

    regulatory_compliance selects the table: aircraft-statutory-certificates,
    organizational-approvals, oem-technical-publication, or personnel-compliance.
    The record with the given id is updated to is_withhold=True.
    """
    try:
        await update_advisory_withhold(
            session=session,
            regulatory_compliance=regulatory_compliance,
            id=id,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "Withhold updated"}


router_advisory.get("/filter-options", response_model=AdvisoryFilterOptionsResponse)(get_advisory_filter_options)
router_advisory.get("", response_model=AdvisoryPagedResponse)(get_advisory)
router_advisory.get("/", response_model=AdvisoryPagedResponse)(get_advisory)
router_advisory.get("/paged", response_model=AdvisoryPagedResponse)(get_advisory_paged)
router_advisory.get("/paged/", response_model=AdvisoryPagedResponse)(get_advisory_paged)
router_advisory.get("/{id}", response_model=AdvisoryDetailResponse)(get_advisory_by_id)
router_advisory.get("/{id}/", response_model=AdvisoryDetailResponse)(get_advisory_by_id)
router_advisory.put("/{id}/{expiry}/", status_code=200)(put_advisory_expiry)
router_advisory.put("/withhold/{id}/{regulatory_compliance}", status_code=200)(put_advisory_withhold)
