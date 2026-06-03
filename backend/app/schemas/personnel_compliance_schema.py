from datetime import date, datetime
from typing import Any, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, validator

from app.models.personnel_compliance import PersonnelComplianceItemType

if TYPE_CHECKING:
    from app.models.personnel_authorization import PersonnelAuthorization
from app.schemas.personnel_authorization_schema import (
    AccountInformationPersonnelSummary,
    AuthorizationScopeBaronSummary,
    AuthorizationScopeCessnaSummary,
    AuthorizationScopeOthersSummary,
    _account_info_to_summary,
    _coerce_optional_scope_id,
)


class PersonnelComplianceBase(BaseModel):
    account_information_id: int
    item_type: PersonnelComplianceItemType
    authorization_scope_cessna_id: Optional[int] = None
    authorization_scope_baron_id: Optional[int] = None
    authorization_scope_others_id: Optional[int] = None
    auth_issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_withhold: bool = False

    class Config:
        orm_mode = True

    @validator(
        "authorization_scope_cessna_id",
        "authorization_scope_baron_id",
        "authorization_scope_others_id",
        pre=True,
    )
    def coerce_scope_ids_to_null(cls, v: Any) -> Optional[int]:
        return _coerce_optional_scope_id(v)


class PersonnelComplianceCreate(PersonnelComplianceBase):
    pass


class PersonnelComplianceUpdate(BaseModel):
    account_information_id: Optional[int] = None
    item_type: Optional[PersonnelComplianceItemType] = None
    authorization_scope_cessna_id: Optional[int] = None
    authorization_scope_baron_id: Optional[int] = None
    authorization_scope_others_id: Optional[int] = None
    auth_issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_withhold: Optional[bool] = None

    class Config:
        orm_mode = True

    @validator(
        "authorization_scope_cessna_id",
        "authorization_scope_baron_id",
        "authorization_scope_others_id",
        pre=True,
    )
    def coerce_scope_ids_to_null(cls, v: Any) -> Optional[int]:
        return _coerce_optional_scope_id(v)


class PersonnelComplianceRead(PersonnelComplianceBase):
    id: int
    auth_initial_doi: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    account_information: Optional[AccountInformationPersonnelSummary] = None
    authorization_scope_cessna: Optional[AuthorizationScopeCessnaSummary] = None
    authorization_scope_baron: Optional[AuthorizationScopeBaronSummary] = None
    authorization_scope_others: Optional[AuthorizationScopeOthersSummary] = None

    class Config:
        orm_mode = True
        use_enum_values = True

    @classmethod
    def from_orm_with_personnel_authorization(
        cls,
        obj: Any,
        pa: Optional["PersonnelAuthorization"] = None,
    ) -> "PersonnelComplianceRead":
        read = cls.from_orm(obj)
        auth_doi = pa.auth_initial_doi if pa is not None else None
        if auth_doi is None:
            acc = getattr(obj, "account_information", None)
            if acc is not None:
                auth_doi = getattr(acc, "auth_initial_doi", None)
        return cls(**{**read.dict(), "auth_initial_doi": auth_doi})

    @validator("account_information", pre=True)
    def account_information_from_orm(cls, v: Any) -> Any:
        if v is None:
            return None
        summary = _account_info_to_summary(v)
        if summary is not None:
            return summary
        return v


class PersonnelCompliancePagedResponse(BaseModel):
    """Response shape for GET list and GET /paged."""

    items: List[PersonnelComplianceRead]
    total: int
    page: int
    pages: int
