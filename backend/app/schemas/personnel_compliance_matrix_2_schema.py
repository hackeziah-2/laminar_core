from datetime import date
from typing import List, Optional

from pydantic import BaseModel

from app.models.personnel_authorization import PersonnelAuthorization
from app.schemas.personnel_authorization_schema import _account_info_to_summary


class PersonnelComplianceMatrix2Item(BaseModel):
    """One matrix row per account_information_id (combined from latest personnel authorization)."""

    account_information_id: int
    authorization_no: Optional[str] = None
    name: str
    position: Optional[str] = None
    lic_no_type: Optional[str] = None
    auth_initial_doi: Optional[date] = None
    auth_issue_date: Optional[date] = None
    auth_expiry_date: Optional[date] = None
    authorization_scope_cessna: Optional[str] = None
    authorization_scope_baron: Optional[str] = None
    authorization_scope_others: Optional[str] = None
    caap_lic_expiry: Optional[date] = None
    hf_training_expiry: Optional[date] = None
    type_training_expiry_cessna: Optional[date] = None
    type_training_expiry_baron: Optional[date] = None

    class Config:
        orm_mode = True

    @classmethod
    def from_personnel_authorization(cls, pa: PersonnelAuthorization) -> "PersonnelComplianceMatrix2Item":
        acc = pa.account_information
        summary = _account_info_to_summary(acc) if acc is not None else None
        name = summary.full_name if summary else ""
        lic = (summary.license if summary else None) or None
        auth_doi = pa.auth_initial_doi
        if auth_doi is None and acc is not None:
            auth_doi = getattr(acc, "auth_initial_doi", None)
        return cls(
            account_information_id=pa.account_information_id,
            authorization_no=summary.auth_stamp if summary else None,
            name=name,
            position=summary.designation if summary else None,
            lic_no_type=lic,
            auth_initial_doi=auth_doi,
            auth_issue_date=pa.auth_issue_date,
            auth_expiry_date=pa.auth_expiry_date,
            authorization_scope_cessna=(
                pa.authorization_scope_cessna.name if pa.authorization_scope_cessna else None
            ),
            authorization_scope_baron=(
                pa.authorization_scope_baron.name if pa.authorization_scope_baron else None
            ),
            authorization_scope_others=(
                pa.authorization_scope_others.name if pa.authorization_scope_others else None
            ),
            caap_lic_expiry=pa.caap_license_expiry,
            hf_training_expiry=pa.human_factors_training_expiry,
            type_training_expiry_cessna=pa.type_training_expiry_cessna,
            type_training_expiry_baron=pa.type_training_expiry_baron,
        )


class PersonnelComplianceMatrix2PagedResponse(BaseModel):
    items: List[PersonnelComplianceMatrix2Item]
    total: int
    page: int
    pages: int
