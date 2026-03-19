"""Aggregate advisory data from aircraft statutory certificates, organizational approvals, OEM technical publications, and personnel authorizations.

PERSONNEL_EXPIRY_LABELS: category_type (display label) -> PersonnelAuthorization attribute name.

ITEM:
  - If from Organizational Approvals: APPROVAL TYPE (certificate__name) (NUMBER) — i.e. certificate name and number, e.g. "CERT NAME (123)".

REMAINING VALIDITY (numeric, expiry - today; positive = days left, <= 0 = expired):
  - If not date_of_expiration, from PERSONNEL AUTHORIZATION: auth_expiry_date - today, human_factors_training_expiry - today, type_training_expiry_cessna - today, type_training_expiry_baron - today.
  - Else: date_of_expiration - today.

Display: if REMAINING VALIDITY <= 0 → "Expired"; elif REMAINING VALIDITY <= 30 → REMAINING VALIDITY (int). Only items with REMAINING VALIDITY <= 30 are returned.
"""
import re

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.aircraft_statutory_certificate import (
    AircraftStatutoryCertificate,
    CategoryTypeEnum as StatutoryCategoryTypeEnum,
)
from app.models.certificate_category_type import CertificateCategoryType
from app.models.oem_item_type import OemItemType
from app.models.oem_technical_publication import (
    OemTechnicalPublication,
    OemTechnicalPublicationCategoryTypeEnum as OemCategoryTypeEnum,
)
from app.models.organizational_approval import OrganizationalApproval
from app.models.personnel_authorization import PersonnelAuthorization
from app.schemas.advisory_schema import AdvisoryItem, RegulatoryComplianceSource

PERSONNEL_EXPIRY_LABELS = {
    "AUTH EXPIRATION": "auth_expiry_date",
    "CESSNA TRAINING": "type_training_expiry_cessna",
    "CAAP LICENSE": "caap_license_expiry",
    "HUMAN FACTORS TRAINING": "human_factors_training_expiry",
    "BARON TRAINING": "type_training_expiry_baron",
}


def _remaining_validity(expiry_date: date | None, today: date) -> int | None:
    """REMAINING VALIDITY = expiry_date - today (positive = days left, <= 0 = expired)."""
    if expiry_date is None:
        return None
    return (expiry_date - today).days


def _remaining_days_display(remaining_validity: int | None) -> Optional[str | int]:
    """If REMAINING_VALIDITY <= 0 → 'Expired'; elif REMAINING_VALIDITY <= 30 → REMAINING_VALIDITY (int)."""
    if remaining_validity is None:
        return None
    if remaining_validity <= 0:
        return "Expired"
    return remaining_validity


def _build_item(
    item: str,
    type_: str,
    expiry: date | None,
    today: date,
    id: Optional[int] = None,
    regulatory_compliance: Optional[RegulatoryComplianceSource] = None,
    category_type: Optional[str] = None,
) -> AdvisoryItem:
    remaining = _remaining_validity(expiry, today)
    return AdvisoryItem(
        id=id,
        regulatory_compliance=regulatory_compliance or "personnel-authorization",
        ITEM=item,
        TYPE=type_,
        EXPIRY=expiry,
        REMAINING_VALIDITY=remaining,
        REMAINING_DAYS=_remaining_days_display(remaining),
        category_type=category_type,
    )


def _normalize_type_filter(type_filter: Optional[str]) -> Optional[str]:
    if not type_filter or not type_filter.strip():
        return None
    value = type_filter.strip().upper().replace(" ", "_")
    if "REGULATORY" in value and "NON_CERT" in value:
        return "REGULATORY_CORRESPONDENCE_NON_CERT"
    if value in {"CERTIFICATE", "LICENSE", "SUBSCRIPTION", "REGULATORY_CORRESPONDENCE_NON_CERT"}:
        return value
    return type_filter.strip()


async def list_advisory_items(
    session: AsyncSession,
    limit: Optional[int] = 10,
    offset: int = 0,
    sort_remaining_validity: Optional[str] = None,
    type_filter: Optional[str] = None,
    item_filter: Optional[str] = None,
) -> Tuple[List[AdvisoryItem], int]:
    today = date.today()
    rows: List[AdvisoryItem] = []

    stmt_certificates = (
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .join(Aircraft, AircraftStatutoryCertificate.aircraft_fk == Aircraft.id)
        .where(AircraftStatutoryCertificate.is_deleted == False)
        .where(Aircraft.is_deleted == False)
        .where(AircraftStatutoryCertificate.date_of_expiration.isnot(None))
    )
    result_certificates = await session.execute(stmt_certificates)
    for certificate in result_certificates.scalars().all():
        registration = certificate.aircraft.registration if certificate.aircraft else ""
        category_type = certificate.category_type.value if certificate.category_type else ""
        item = (f"{category_type} ({registration})" if category_type and registration else (category_type or registration)).upper()
        advisory_type = (
            "REGULATORY_CORRESPONDENCE_NON_CERT"
            if certificate.category_type
            in (
                StatutoryCategoryTypeEnum.MARKING_RESERVATION,
                StatutoryCategoryTypeEnum.BINARY_CODE_24BIT,
            )
            else "CERTIFICATE"
        )
        rows.append(
            _build_item(
                item,
                advisory_type,
                certificate.date_of_expiration,
                today,
                id=certificate.id,
                regulatory_compliance="aircraft-statutory-certificates",
                category_type=category_type
            )
        )

    stmt_approvals = (
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .join(CertificateCategoryType, OrganizationalApproval.certificate_fk == CertificateCategoryType.id)
        .where(OrganizationalApproval.is_deleted == False)
        .where(CertificateCategoryType.is_deleted == False)
        .where(OrganizationalApproval.date_of_expiration.isnot(None))
    )
    result_approvals = await session.execute(stmt_approvals)
    for approval in result_approvals.scalars().all():
        # ITEM from Organizational Approvals: APPROVAL TYPE (certificate__name) (NUMBER)
        cert_name = (approval.certificate.name if approval.certificate else "").strip()
        num = (approval.number or "").strip()
        if cert_name and num:
            item_name = f"{cert_name} ({num})".upper()
        else:
            item_name = (cert_name or num or "").upper()
        category_type_approval = cert_name or ""
        rows.append(
            _build_item(
                item_name,
                "CERTIFICATE",
                approval.date_of_expiration,
                today,
                id=approval.id,
                regulatory_compliance="organizational-approvals",
                category_type=category_type_approval,
            )
        )

    stmt_publications = (
        select(OemTechnicalPublication)
        .options(selectinload(OemTechnicalPublication.item))
        .join(OemItemType, OemTechnicalPublication.item_fk == OemItemType.id)
        .where(OemTechnicalPublication.is_deleted == False)
        .where(OemItemType.is_deleted == False)
        .where(OemTechnicalPublication.date_of_expiration.isnot(None))
    )
    result_publications = await session.execute(stmt_publications)
    for publication in result_publications.scalars().all():
        item_name = (publication.item.name if publication.item else "").upper()
        advisory_type = (
            "SUBSCRIPTION"
            if publication.category_type == OemCategoryTypeEnum.SUBSCRIPTION
            else publication.category_type.value if publication.category_type else "CERTIFICATE"
        )
        category_type_pub = publication.category_type.value if publication.category_type else item_name or ""
        rows.append(
            _build_item(
                item_name,
                advisory_type,
                publication.date_of_expiration,
                today,
                id=publication.id,
                regulatory_compliance="oem-technical-publication",
                category_type=category_type_pub,
            )
        )

    stmt_personnel = (
        select(PersonnelAuthorization)
        .options(selectinload(PersonnelAuthorization.account_information))
        .join(AccountInformation, PersonnelAuthorization.account_information_id == AccountInformation.id)
        .where(PersonnelAuthorization.is_deleted == False)
        .where(AccountInformation.is_deleted == False)
    )
    result_personnel = await session.execute(stmt_personnel)
    for personnel in result_personnel.scalars().all():
        account = personnel.account_information
        full_name = ""
        if account:
            full_name = f"{account.first_name or ''} {account.last_name or ''}".strip() or getattr(account, "username", "") or ""
        full_name_upper = full_name.upper()

        # PERSONNEL AUTHORIZATION: ITEM = "LABEL (FULL_NAME)" per expiry type; all in CAPS.
        personnel_expiry_labels = (
            (personnel.auth_expiry_date, "AUTH EXPIRATION"),
            (personnel.type_training_expiry_cessna, "CESSNA TRAINING"),
            (personnel.caap_license_expiry, "CAAP LICENSE"),
            (personnel.human_factors_training_expiry, "HUMAN FACTORS TRAINING"),
            (personnel.type_training_expiry_baron, "BARON TRAINING"),
        )
        for expiry_date, label in personnel_expiry_labels:
            if expiry_date is not None:
                item = f"{label} ({full_name_upper})"
                advisory_type = "LICENSE" if label == "CAAP LICENSE" else "CERTIFICATE"
                rows.append(
                    _build_item(
                        item,
                        advisory_type,
                        expiry_date,
                        today,
                        id=personnel.id,
                        regulatory_compliance="personnel-authorization",
                        category_type=label,
                    )
                )

    normalized_type = _normalize_type_filter(type_filter)
    if normalized_type is not None:
        rows = [row for row in rows if row.TYPE == normalized_type]

    # Search by ITEM: case-insensitive substring match
    if item_filter and item_filter.strip():
        needle = item_filter.strip().upper()
        rows = [row for row in rows if row.ITEM and needle in (row.ITEM or "").upper()]

    # Only items with REMAINING VALIDITY <= 30 (expiry - today; positive = days left)
    rows = [row for row in rows if row.REMAINING_VALIDITY is not None and row.REMAINING_VALIDITY <= 30]

    # Sort by REMAINING_VALIDITY: asc = lowest first (0, 1, 2, ...), desc = highest first (30, ..., 0)
    def _rv(row: AdvisoryItem) -> int:
        v = row.REMAINING_VALIDITY
        return v if v is not None else 0

    sort_desc = (sort_remaining_validity or "asc").strip().lower() == "desc"
    if sort_desc:
        rows.sort(key=lambda row: (-_rv(row), (row.ITEM or "")))
    else:
        rows.sort(key=lambda row: (_rv(row), (row.ITEM or "")))

    total = len(rows)
    if limit is None:
        return rows, total
    return rows[offset : offset + limit], total


async def update_advisory_expiry(
    session: AsyncSession,
    regulatory_compliance: RegulatoryComplianceSource,
    id: int,
    expiry: date,
    category_type: Optional[str] = None,
) -> None:
    """Update expiry for an advisory item by id and regulatory_compliance.

    For aircraft-statutory-certificates, organizational-approvals, oem-technical-publication:
      set date_of_expiration = expiry.

    For personnel-authorization: use category_type to pick the field (PERSONNEL_EXPIRY_LABELS)
      and set that attribute to expiry.

    Raises:
        ValueError: If advisory item not found or invalid category_type for personnel.
    """
    if regulatory_compliance != "personnel-authorization":
        if regulatory_compliance == "aircraft-statutory-certificates":
            stmt = select(AircraftStatutoryCertificate).where(
                AircraftStatutoryCertificate.id == id,
                AircraftStatutoryCertificate.is_deleted == False,
            )
            result = await session.execute(stmt)
            instance = result.scalars().one_or_none()
        elif regulatory_compliance == "organizational-approvals":
            stmt = select(OrganizationalApproval).where(
                OrganizationalApproval.id == id,
                OrganizationalApproval.is_deleted == False,
            )
            result = await session.execute(stmt)
            instance = result.scalars().one_or_none()
        elif regulatory_compliance == "oem-technical-publication":
            stmt = select(OemTechnicalPublication).where(
                OemTechnicalPublication.id == id,
                OemTechnicalPublication.is_deleted == False,
            )
            result = await session.execute(stmt)
            instance = result.scalars().one_or_none()
        else:
            raise ValueError("Invalid regulatory_compliance")
        if not instance:
            raise ValueError("Advisory item not found")
        instance.date_of_expiration = expiry
    else:
        personnel_expiry_labels = PERSONNEL_EXPIRY_LABELS
        print(personnel_expiry_labels, "personnel_expiry_labels")
        print(category_type, "category_type")
        category_type = (category_type or "").strip()
        if not category_type:
            raise ValueError("Invalid category_type")
        field_name = personnel_expiry_labels.get(category_type)
        if not field_name:
            raise ValueError("Invalid category_type")
        stmt = select(PersonnelAuthorization).where(
            PersonnelAuthorization.id == id,
            PersonnelAuthorization.is_deleted == False,
        )
        result = await session.execute(stmt)
        personnel_instance = result.scalars().one_or_none()
        if not personnel_instance:
            raise ValueError("Advisory item not found")
        setattr(personnel_instance, field_name, expiry)
    await session.commit()
