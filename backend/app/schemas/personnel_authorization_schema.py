from datetime import date, datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, root_validator, validator


class AccountInformationNameSummary(BaseModel):
    id: int
    first_name: str
    last_name: str

    class Config:
        orm_mode = True


class AccountInformationPersonnelSummary(BaseModel):
    """Account info for personnel-authorization GET: designation, auth_stamp, full_name, license."""
    id: int
    designation: Optional[str] = None
    auth_stamp: Optional[str] = None
    full_name: str  # "last_name, first_name"
    license: Optional[str] = None

    class Config:
        orm_mode = True

    @root_validator(pre=True)
    def build_from_orm(cls, values: Any) -> Any:
        """Build from AccountInformation ORM or dict: full_name as last_name, first_name; license from license_no."""
        # Already has full_name (e.g. from a previous validator or dict)
        if isinstance(values, dict) and "full_name" in values and values["full_name"] is not None:
            return values
        # ORM object: has first_name / last_name attributes
        if hasattr(values, "first_name") and hasattr(values, "last_name"):
            first = getattr(values, "first_name", None) or ""
            last = getattr(values, "last_name", None) or ""
            full_name = ", ".join(filter(None, [last, first]))
            return {
                "id": getattr(values, "id", None),
                "designation": getattr(values, "designation", None),
                "auth_stamp": getattr(values, "auth_stamp", None),
                "full_name": full_name,
                "license": getattr(values, "license_no", None),
            }
        # Dict from ORM (e.g. only some keys present): build full_name from first_name/last_name
        if isinstance(values, dict):
            first = values.get("first_name") or ""
            last = values.get("last_name") or ""
            full_name = ", ".join(filter(None, [last, first]))
            out = dict(values)
            out["full_name"] = full_name
            out.setdefault("license", values.get("license_no"))
            return out
        return values


class AuthorizationScopeCessnaSummary(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class AuthorizationScopeBaronSummary(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class AuthorizationScopeOthersSummary(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


def _coerce_optional_scope_id(v: Any) -> Optional[int]:
    """Coerce empty string or other falsy non-int to None for scope FK fields."""
    if v is None:
        return None
    if v == "" or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, int):
        return v
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


class PersonnelAuthorizationBase(BaseModel):
    account_information_id: int
    authorization_scope_cessna_id: Optional[int] = None
    authorization_scope_baron_id: Optional[int] = None
    authorization_scope_others_id: Optional[int] = None
    auth_initial_doi: Optional[date] = None
    auth_issue_date: Optional[date] = None
    auth_expiry_date: Optional[date] = None
    caap_license_expiry: Optional[date] = None
    human_factors_training_expiry: Optional[date] = None
    type_training_expiry_cessna: Optional[date] = None
    type_training_expiry_baron: Optional[date] = None

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


class PersonnelAuthorizationCreate(PersonnelAuthorizationBase):
    pass


class PersonnelAuthorizationUpdate(BaseModel):
    account_information_id: Optional[int] = None
    authorization_scope_cessna_id: Optional[int] = None
    authorization_scope_baron_id: Optional[int] = None
    authorization_scope_others_id: Optional[int] = None
    auth_initial_doi: Optional[date] = None
    auth_issue_date: Optional[date] = None
    auth_expiry_date: Optional[date] = None
    caap_license_expiry: Optional[date] = None
    human_factors_training_expiry: Optional[date] = None
    type_training_expiry_cessna: Optional[date] = None
    type_training_expiry_baron: Optional[date] = None

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


def _account_info_to_summary(obj: Any) -> Optional[AccountInformationPersonnelSummary]:
    """Build AccountInformationPersonnelSummary from ORM or dict; return None if obj is None."""
    if obj is None:
        return None
    if hasattr(obj, "first_name") and hasattr(obj, "last_name"):
        first = getattr(obj, "first_name", None) or ""
        last = getattr(obj, "last_name", None) or ""
        full_name = ", ".join(filter(None, [last, first]))
        return AccountInformationPersonnelSummary(
            id=getattr(obj, "id", None),
            designation=getattr(obj, "designation", None),
            auth_stamp=getattr(obj, "auth_stamp", None),
            full_name=full_name,
            license=getattr(obj, "license_no", None),
        )
    if isinstance(obj, dict):
        first = obj.get("first_name") or ""
        last = obj.get("last_name") or ""
        full_name = ", ".join(filter(None, [last, first]))
        return AccountInformationPersonnelSummary(
            id=obj.get("id"),
            designation=obj.get("designation"),
            auth_stamp=obj.get("auth_stamp"),
            full_name=full_name,
            license=obj.get("license") or obj.get("license_no"),
        )
    return None


class PersonnelAuthorizationRead(PersonnelAuthorizationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    account_information: Optional[AccountInformationPersonnelSummary] = None
    authorization_scope_cessna: Optional[AuthorizationScopeCessnaSummary] = None
    authorization_scope_baron: Optional[AuthorizationScopeBaronSummary] = None
    authorization_scope_others: Optional[AuthorizationScopeOthersSummary] = None

    class Config:
        orm_mode = True

    @validator("account_information", pre=True)
    def account_information_from_orm(cls, v: Any) -> Any:
        """Ensure account_information is built with full_name when loading from ORM."""
        if v is None:
            return None
        summary = _account_info_to_summary(v)
        if summary is not None:
            return summary
        return v
