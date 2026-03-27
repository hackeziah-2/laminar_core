from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.models.personnel_authorization import PersonnelAuthorization
from app.models.personnel_compliance import PersonnelCompliance, PersonnelComplianceItemType
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
    others_expiry_date: Optional[date] = None

    class Config:
        orm_mode = True

    @classmethod
    def from_personnel_authorization(
        cls,
        pa: PersonnelAuthorization,
        *,
        others_expiry_date: Optional[date] = None,
        compliance_by_type: Optional[Dict[PersonnelComplianceItemType, PersonnelCompliance]] = None,
    ) -> "PersonnelComplianceMatrix2Item":
        acc = pa.account_information
        summary = _account_info_to_summary(acc) if acc is not None else None
        name = summary.full_name if summary else ""
        lic = (summary.license if summary else None) or None
        auth_doi = pa.auth_initial_doi
        if auth_doi is None and acc is not None:
            auth_doi = getattr(acc, "auth_initial_doi", None)

        pc_map = compliance_by_type or {}
        pc_caap = pc_map.get(PersonnelComplianceItemType.CAAP_LICENSE)
        pc_hf = pc_map.get(PersonnelComplianceItemType.HF_TRAINING)
        pc_cessna = pc_map.get(PersonnelComplianceItemType.CESSNA)
        pc_baron = pc_map.get(PersonnelComplianceItemType.BARON)
        pc_others = pc_map.get(PersonnelComplianceItemType.OTHERS)

        def coalesce_date(
            auth_val: Optional[date], pc_row: Optional[PersonnelCompliance]
        ) -> Optional[date]:
            if auth_val is not None:
                return auth_val
            if pc_row is not None and pc_row.expiry_date is not None:
                return pc_row.expiry_date
            return None

        scope_cessna = (
            pa.authorization_scope_cessna.name if pa.authorization_scope_cessna else None
        )
        if scope_cessna is None and pc_cessna and pc_cessna.authorization_scope_cessna:
            scope_cessna = pc_cessna.authorization_scope_cessna.name

        scope_baron = (
            pa.authorization_scope_baron.name if pa.authorization_scope_baron else None
        )
        if scope_baron is None and pc_baron and pc_baron.authorization_scope_baron:
            scope_baron = pc_baron.authorization_scope_baron.name

        scope_others = (
            pa.authorization_scope_others.name if pa.authorization_scope_others else None
        )
        if scope_others is None and pc_others and pc_others.authorization_scope_others:
            scope_others = pc_others.authorization_scope_others.name

        others_exp = others_expiry_date
        if others_exp is None and pc_others is not None:
            others_exp = pc_others.expiry_date

        return cls(
            account_information_id=pa.account_information_id,
            authorization_no=summary.auth_stamp if summary else None,
            name=name,
            position=summary.designation if summary else None,
            lic_no_type=lic,
            auth_initial_doi=auth_doi,
            auth_issue_date=pa.auth_issue_date,
            auth_expiry_date=pa.auth_expiry_date,
            authorization_scope_cessna=scope_cessna,
            authorization_scope_baron=scope_baron,
            authorization_scope_others=scope_others,
            caap_lic_expiry=coalesce_date(pa.caap_license_expiry, pc_caap),
            hf_training_expiry=coalesce_date(pa.human_factors_training_expiry, pc_hf),
            type_training_expiry_cessna=coalesce_date(
                pa.type_training_expiry_cessna, pc_cessna
            ),
            type_training_expiry_baron=coalesce_date(
                pa.type_training_expiry_baron, pc_baron
            ),
            others_expiry_date=others_exp,
        )


class PersonnelComplianceMatrix2PagedResponse(BaseModel):
    items: List[PersonnelComplianceMatrix2Item]
    total: int
    page: int
    pages: int
