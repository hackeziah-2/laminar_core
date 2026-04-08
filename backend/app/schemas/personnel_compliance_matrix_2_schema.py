from datetime import date
from typing import Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel

from app.models.personnel_authorization import PersonnelAuthorization
from app.models.personnel_compliance import PersonnelCompliance, PersonnelComplianceItemType

if TYPE_CHECKING:
    from app.models.account import AccountInformation
from app.schemas.personnel_authorization_schema import _account_info_to_summary


def _personnel_compliance_matrix_date(pc: PersonnelCompliance) -> Optional[date]:
    """Effective expiry for matrix columns, keyed by personnel_compliance.item_type."""
    if pc.item_type == PersonnelComplianceItemType.AUTH_EXPIRY:
        return pc.auth_issue_date
    return pc.expiry_date


def _coalesce_compliance_then_auth(
    pc_row: Optional[PersonnelCompliance], auth_val: Optional[date]
) -> Optional[date]:
    if pc_row is not None:
        d = _personnel_compliance_matrix_date(pc_row)
        if d is not None:
            return d
    return auth_val


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
    def from_account_and_personnel_authorization(
        cls,
        account: "AccountInformation",
        pa: Optional[PersonnelAuthorization],
        *,
        others_expiry_date: Optional[date] = None,
        compliance_by_type: Optional[Dict[PersonnelComplianceItemType, PersonnelCompliance]] = None,
    ) -> "PersonnelComplianceMatrix2Item":
        acc = account
        summary = _account_info_to_summary(acc) if acc is not None else None
        name = summary.full_name if summary else ""
        lic = (summary.license if summary else None) or None
        auth_doi = pa.auth_initial_doi if pa is not None else None
        if auth_doi is None and acc is not None:
            auth_doi = getattr(acc, "auth_initial_doi", None)

        pc_map = compliance_by_type or {}
        pc_auth_expiry = pc_map.get(PersonnelComplianceItemType.AUTH_EXPIRY)
        pc_caap = pc_map.get(PersonnelComplianceItemType.CAAP_LICENSE)
        pc_hf = pc_map.get(PersonnelComplianceItemType.HF_TRAINING)
        pc_cessna = pc_map.get(PersonnelComplianceItemType.CESSNA)
        pc_baron = pc_map.get(PersonnelComplianceItemType.BARON)
        pc_others = pc_map.get(PersonnelComplianceItemType.OTHERS)

        scope_cessna = (
            pa.authorization_scope_cessna.name
            if pa is not None and pa.authorization_scope_cessna
            else None
        )
        if scope_cessna is None and pc_cessna and pc_cessna.authorization_scope_cessna:
            scope_cessna = pc_cessna.authorization_scope_cessna.name

        scope_baron = (
            pa.authorization_scope_baron.name
            if pa is not None and pa.authorization_scope_baron
            else None
        )
        if scope_baron is None and pc_baron and pc_baron.authorization_scope_baron:
            scope_baron = pc_baron.authorization_scope_baron.name

        scope_others = (
            pa.authorization_scope_others.name
            if pa is not None and pa.authorization_scope_others
            else None
        )
        if scope_others is None and pc_others and pc_others.authorization_scope_others:
            scope_others = pc_others.authorization_scope_others.name

        others_exp = others_expiry_date
        if others_exp is None:
            others_exp = _coalesce_compliance_then_auth(pc_others, None)

        pa_auth_expiry = pa.auth_expiry_date if pa is not None else None
        pa_issue = pa.auth_issue_date if pa is not None else None
        pa_caap = pa.caap_license_expiry if pa is not None else None
        pa_hf = pa.human_factors_training_expiry if pa is not None else None
        pa_tc = pa.type_training_expiry_cessna if pa is not None else None
        pa_tb = pa.type_training_expiry_baron if pa is not None else None

        return cls(
            account_information_id=acc.id,
            authorization_no=summary.auth_stamp if summary else None,
            name=name,
            position=summary.designation if summary else None,
            lic_no_type=lic,
            auth_initial_doi=auth_doi,
            auth_issue_date=pa_issue,
            auth_expiry_date=_coalesce_compliance_then_auth(
                pc_auth_expiry, pa_auth_expiry
            ),
            authorization_scope_cessna=scope_cessna,
            authorization_scope_baron=scope_baron,
            authorization_scope_others=scope_others,
            caap_lic_expiry=_coalesce_compliance_then_auth(pc_caap, pa_caap),
            hf_training_expiry=_coalesce_compliance_then_auth(pc_hf, pa_hf),
            type_training_expiry_cessna=_coalesce_compliance_then_auth(pc_cessna, pa_tc),
            type_training_expiry_baron=_coalesce_compliance_then_auth(pc_baron, pa_tb),
            others_expiry_date=others_exp,
        )

    @classmethod
    def from_personnel_authorization(
        cls,
        pa: PersonnelAuthorization,
        *,
        others_expiry_date: Optional[date] = None,
        compliance_by_type: Optional[Dict[PersonnelComplianceItemType, PersonnelCompliance]] = None,
    ) -> "PersonnelComplianceMatrix2Item":
        acc = pa.account_information
        if acc is None:
            raise ValueError("PersonnelAuthorization.account_information must be loaded")
        return cls.from_account_and_personnel_authorization(
            acc,
            pa,
            others_expiry_date=others_expiry_date,
            compliance_by_type=compliance_by_type,
        )


class PersonnelComplianceMatrix2PagedResponse(BaseModel):
    items: List[PersonnelComplianceMatrix2Item]
    total: int
    page: int
    pages: int
