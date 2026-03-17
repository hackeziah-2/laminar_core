"""Aggregate advisory data from aircraft statutory certificates, organizational approvals, OEM technical publications, and personnel authorizations."""

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.aircraft_statutory_certificate import (
    AircraftStatutoryCertificate,
    CategoryTypeEnum as StatutoryCategoryTypeEnum,
)
from app.models.aircraft import Aircraft
from app.models.organizational_approval import OrganizationalApproval
from app.models.certificate_category_type import CertificateCategoryType
from app.models.oem_technical_publication import (
    OemTechnicalPublication,
    OemTechnicalPublicationCategoryTypeEnum as OemCategoryTypeEnum,
)
from app.models.oem_item_type import OemItemType
from app.models.personnel_authorization import PersonnelAuthorization
from app.models.account import AccountInformation
from app.schemas.advisory_schema import (
    AdvisoryItem,
    AdvisoryItemGroup,
    AdvisoryExpiryEntry,
    AdvisoryExpiryEntryWithItem,
    AdvisoryTypeGroup,
)


def _remaining_validity(expiry_date: date | None, today: date) -> int | None:
    """Remaining validity = (today - date_of_expiration).days; negative = days left, positive = overdue."""
    if expiry_date is None:
        return None
    return (today - expiry_date).days


def _advisory_item(item: str, type_: str, expiry: date | None, today: date) -> AdvisoryItem:
    return AdvisoryItem(
        item=item,
        type=type_,
        expiry=expiry,
        remaining_validity=_remaining_validity(expiry, today),
    )


# Normalize filter value: accept value or label; stored types are CERTIFICATE, REGULATORY_CORRESPONDENCE_NON_CERT, LICENSE, SUBSCRIPTION
def _normalize_type_filter(type_filter: Optional[str]) -> Optional[str]:
    if not type_filter or not type_filter.strip():
        return None
    v = type_filter.strip().upper().replace(" ", "_")
    if "REGULATORY" in v and "NON_CERT" in v:
        return "REGULATORY_CORRESPONDENCE_NON_CERT"
    if v in ("CERTIFICATE", "LICENSE", "SUBSCRIPTION", "REGULATORY_CORRESPONDENCE_NON_CERT"):
        return v
    return type_filter.strip()


async def list_advisory_items(
    session: AsyncSession,
    limit: Optional[int] = 10,
    offset: int = 0,
    sort_expiry_asc: bool = True,
    type_filter: Optional[str] = None,
) -> Tuple[List[AdvisoryItem], int]:
    """
    Aggregate advisory rows from:
    - Aircraft Statutory Certificates (ITEM=registration, TYPE=REGULATORY_CORRESPONDENCE_NON_CERT or CERTIFICATE)
    - Organizational Approvals (ITEM=certificate name, TYPE=CERTIFICATE)
    - OEM Technical Publications (ITEM=item type name, TYPE=SUBSCRIPTION or category_type)
    - Personnel Authorization (ITEM=person name, TYPE=LICENSE for CAAP LIC EXPIRY else CERTIFICATE)
    Optionally filter by type: CERTIFICATE, REGULATORY_CORRESPONDENCE_NON_CERT, LICENSE, SUBSCRIPTION.
    Sort by expiry and return paginated items.
    """
    today = date.today()
    rows: List[AdvisoryItem] = []

    # 1) Aircraft Statutory Certificates: ITEM = aircraft.registration, TYPE = REGULATORY_CORRESPONDENCE_NON_CERT if MARKING_RESERVATION or BINARY_CODE_24BIT else CERTIFICATE
    stmt_asc = (
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .join(Aircraft, AircraftStatutoryCertificate.aircraft_fk == Aircraft.id)
        .where(AircraftStatutoryCertificate.is_deleted == False)
        .where(Aircraft.is_deleted == False)
        .where(AircraftStatutoryCertificate.date_of_expiration.isnot(None))
    )
    result_asc = await session.execute(stmt_asc)
    certs = result_asc.scalars().all()
    for c in certs:
        reg = c.aircraft.registration if c.aircraft else ""
        if c.category_type in (
            StatutoryCategoryTypeEnum.MARKING_RESERVATION,
            StatutoryCategoryTypeEnum.BINARY_CODE_24BIT,
        ):
            type_val = "REGULATORY_CORRESPONDENCE_NON_CERT"
        else:
            type_val = "CERTIFICATE"
        rows.append(
            _advisory_item(reg, type_val, c.date_of_expiration, today)
        )

    # 2) Organizational Approvals: ITEM = certificate name, TYPE = CERTIFICATE
    stmt_oa = (
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .join(CertificateCategoryType, OrganizationalApproval.certificate_fk == CertificateCategoryType.id)
        .where(OrganizationalApproval.is_deleted == False)
        .where(CertificateCategoryType.is_deleted == False)
        .where(OrganizationalApproval.date_of_expiration.isnot(None))
    )
    result_oa = await session.execute(stmt_oa)
    approvals = result_oa.scalars().all()
    for oa in approvals:
        name = oa.certificate.name if oa.certificate else (oa.number or "")
        rows.append(
            _advisory_item(name, "CERTIFICATE", oa.date_of_expiration, today)
        )

    # 3) OEM Technical Publications: ITEM = item type name, TYPE = SUBSCRIPTION if category_type SUBSCRIPTION else category_type value
    stmt_oem = (
        select(OemTechnicalPublication)
        .options(selectinload(OemTechnicalPublication.item))
        .join(OemItemType, OemTechnicalPublication.item_fk == OemItemType.id)
        .where(OemTechnicalPublication.is_deleted == False)
        .where(OemItemType.is_deleted == False)
        .where(OemTechnicalPublication.date_of_expiration.isnot(None))
    )
    result_oem = await session.execute(stmt_oem)
    pubs = result_oem.scalars().all()
    for pub in pubs:
        item_name = pub.item.name if pub.item else ""
        if pub.category_type == OemCategoryTypeEnum.SUBSCRIPTION:
            type_val = "SUBSCRIPTION"
        else:
            type_val = pub.category_type.value if pub.category_type else "CERTIFICATE"
        rows.append(
            _advisory_item(item_name, type_val, pub.date_of_expiration, today)
        )

    # 4) Personnel Authorization: ITEM = account first_name + last_name, one row per expiry date; TYPE = LICENSE for caap_license_expiry else CERTIFICATE
    stmt_pa = (
        select(PersonnelAuthorization)
        .options(selectinload(PersonnelAuthorization.account_information))
        .join(AccountInformation, PersonnelAuthorization.account_information_id == AccountInformation.id)
        .where(PersonnelAuthorization.is_deleted == False)
        .where(AccountInformation.is_deleted == False)
    )
    result_pa = await session.execute(stmt_pa)
    personnels = result_pa.scalars().all()
    for pa in personnels:
        acc = pa.account_information
        name = ""
        if acc:
            name = f"{acc.first_name or ''} {acc.last_name or ''}".strip() or getattr(acc, "username", "") or ""
        expiry_fields = [
            (pa.auth_expiry_date, "CERTIFICATE"),
            (pa.caap_license_expiry, "LICENSE"),
            (pa.human_factors_training_expiry, "CERTIFICATE"),
            (pa.type_training_expiry_cessna, "CERTIFICATE"),
            (pa.type_training_expiry_baron, "CERTIFICATE"),
        ]
        for expiry_date, type_val in expiry_fields:
            if expiry_date is not None:
                rows.append(
                    _advisory_item(name, type_val, expiry_date, today)
                )

    # Filter by type if requested
    normalized_type = _normalize_type_filter(type_filter)
    if normalized_type is not None:
        rows = [r for r in rows if r.type == normalized_type]

    # Sort by expiry (nulls last). Asc = earliest first, desc = latest first.
    def sort_key_asc(r: AdvisoryItem):
        return (r.expiry is None, r.expiry or date.max, r.item)

    def sort_key_desc(r: AdvisoryItem):
        return (r.expiry is None, -(r.expiry or date.min).toordinal() if r.expiry else 0, r.item)

    if sort_expiry_asc:
        rows.sort(key=sort_key_asc)
    else:
        rows.sort(key=sort_key_desc)

    total = len(rows)
    if limit is None:
        return rows, total
    page_items = rows[offset : offset + limit]
    return page_items, total


def _group_rows_by_item_type(
    rows: List[AdvisoryItem],
    sort_expiry_asc: bool,
) -> List[AdvisoryItemGroup]:
    """Group flat advisory rows by (item, type) and annotate with expiries."""
    from collections import defaultdict

    grouped: dict[tuple[str, str], List[AdvisoryExpiryEntry]] = defaultdict(list)
    for r in rows:
        key = (r.item, r.type)
        grouped[key].append(
            AdvisoryExpiryEntry(
                expiry=r.expiry,
                remaining_validity=r.remaining_validity,
            )
        )
    # Sort expiries within each group
    for key in grouped:
        entries = grouped[key]
        entries.sort(
            key=lambda e: (e.expiry is None, e.expiry or date.max),
            reverse=not sort_expiry_asc,
        )
    # Build groups; sort groups by earliest (or latest) expiry in group, then item, then type
    def group_sort_key(item_type: tuple[str, str]) -> tuple:
        item, type_ = item_type
        entries = grouped[item_type]
        min_expiry = None
        for e in entries:
            if e.expiry is not None:
                min_expiry = min(min_expiry, e.expiry) if min_expiry else e.expiry
        if sort_expiry_asc:
            return (min_expiry is None, min_expiry or date.max, item, type_)
        return (min_expiry is None, -(min_expiry or date.min).toordinal(), item, type_)

    sorted_keys = sorted(grouped.keys(), key=group_sort_key)
    return [
        AdvisoryItemGroup(
            item=item,
            type=type_,
            expiries=grouped[(item, type_)],
        )
        for item, type_ in sorted_keys
    ]


def _group_rows_by_type(
    rows: List[AdvisoryItem],
    sort_expiry_asc: bool,
) -> List[AdvisoryTypeGroup]:
    """Group flat advisory rows by type; each group lists (item, expiry, remaining_validity) entries."""
    from collections import defaultdict

    grouped: dict[str, List[AdvisoryExpiryEntryWithItem]] = defaultdict(list)
    for r in rows:
        grouped[r.type].append(
            AdvisoryExpiryEntryWithItem(
                item=r.item,
                expiry=r.expiry,
                remaining_validity=r.remaining_validity,
            )
        )
    # Sort entries within each group by expiry
    for type_key in grouped:
        entries = grouped[type_key]
        entries.sort(
            key=lambda e: (e.expiry is None, e.expiry or date.max, e.item),
            reverse=not sort_expiry_asc,
        )
    # Sort groups by earliest expiry in group, then type name
    def group_sort_key(type_key: str) -> tuple:
        entries = grouped[type_key]
        min_expiry = None
        for e in entries:
            if e.expiry is not None:
                min_expiry = min(min_expiry, e.expiry) if min_expiry else e.expiry
        if sort_expiry_asc:
            return (min_expiry is None, min_expiry or date.max, type_key)
        return (min_expiry is None, -(min_expiry or date.min).toordinal(), type_key)

    sorted_types = sorted(grouped.keys(), key=group_sort_key)
    return [
        AdvisoryTypeGroup(type=type_key, entries=grouped[type_key])
        for type_key in sorted_types
    ]


async def list_advisory_items_grouped(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    sort_expiry_asc: bool = True,
    type_filter: Optional[str] = None,
) -> Tuple[List[AdvisoryItemGroup], int]:
    """
    Same as list_advisory_items but grouped by (item, type). Each group lists all
    expiries for that item+type. Pagination applies to groups.
    """
    rows, _ = await list_advisory_items(
        session=session,
        limit=None,
        offset=0,
        sort_expiry_asc=sort_expiry_asc,
        type_filter=type_filter,
    )
    groups = _group_rows_by_item_type(rows, sort_expiry_asc)
    total = len(groups)
    page_groups = groups[offset : offset + limit]
    return page_groups, total


async def list_advisory_items_grouped_by_type(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    sort_expiry_asc: bool = True,
    type_filter: Optional[str] = None,
) -> Tuple[List[AdvisoryTypeGroup], int]:
    """
    Same as list_advisory_items but grouped by type only. Each group lists all
    (item, expiry, remaining_validity) entries for that type. Pagination applies to type groups.
    """
    rows, _ = await list_advisory_items(
        session=session,
        limit=None,
        offset=0,
        sort_expiry_asc=sort_expiry_asc,
        type_filter=type_filter,
    )
    type_groups = _group_rows_by_type(rows, sort_expiry_asc)
    total = len(type_groups)
    page_groups = type_groups[offset : offset + limit]
    return page_groups, total
