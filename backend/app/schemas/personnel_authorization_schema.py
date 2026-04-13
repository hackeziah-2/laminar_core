from datetime import date, datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, root_validator, validator


def _format_personnel_account_full_name(
    last: str, first: str, middle: Optional[str] = None
) -> str:
    """Same rule as AccountInformationByAuthStamp: last_name, first_name [, middle_name]."""
    parts = [last or "", first or ""]
    if middle and str(middle).strip():
        parts.append(str(middle).strip())
    return ", ".join(p for p in parts if p) or ""


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
        if hasattr(values, "get") and callable(values.get):
            # dict or Pydantic GetterDict (ORM from_orm)
            first = values.get("first_name") or getattr(values, "first_name", "") or ""
            last = values.get("last_name") or getattr(values, "last_name", "") or ""
            middle = values.get("middle_name") or getattr(values, "middle_name", "") or None
            formatted = _format_personnel_account_full_name(last, first, middle)
            explicit = values.get("full_name")
            explicit_str = str(explicit).strip() if explicit is not None else ""
            if formatted:
                full_name = formatted
            elif explicit_str:
                full_name = explicit_str
            else:
                username = values.get("username") or getattr(values, "username", "") or ""
                full_name = str(username).strip()

            if isinstance(values, dict):
                out = dict(values)
                out["full_name"] = full_name
                out.setdefault("license", values.get("license_no"))
                return out
            return {
                "id": values.get("id"),
                "designation": values.get("designation"),
                "auth_stamp": values.get("auth_stamp"),
                "full_name": full_name,
                "license": values.get("license_no") or values.get("license"),
            }

        first = getattr(values, "first_name", None) or ""
        last = getattr(values, "last_name", None) or ""
        middle = getattr(values, "middle_name", None)
        full_name = _format_personnel_account_full_name(last, first, middle)
        if not full_name:
            prop = getattr(values, "full_name", None)
            if prop is not None and str(prop).strip():
                full_name = str(prop).strip()
        if not full_name:
            full_name = str(getattr(values, "username", None) or "").strip()
        return {
            "id": getattr(values, "id", None),
            "designation": getattr(values, "designation", None),
            "auth_stamp": getattr(values, "auth_stamp", None),
            "full_name": full_name,
            "license": getattr(values, "license_no", None),
        }


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


def _account_info_to_summary(obj: Any) -> Optional[AccountInformationPersonnelSummary]:
    """Build AccountInformationPersonnelSummary from ORM, Pydantic GetterDict, or dict."""
    if obj is None:
        return None

    if isinstance(obj, dict):
        first = str(obj.get("first_name") or "").strip()
        last = str(obj.get("last_name") or "").strip()
        middle = obj.get("middle_name")
        if middle is not None:
            middle = str(middle).strip() or None
        formatted = _format_personnel_account_full_name(last, first, middle)
        existing = str(obj.get("full_name") or "").strip()
        if formatted:
            full_name = formatted
        elif existing:
            full_name = existing
        else:
            full_name = str(obj.get("username") or "").strip()
        license_val = obj.get("license_no") or obj.get("license")
        return AccountInformationPersonnelSummary(
            id=obj.get("id"),
            designation=obj.get("designation"),
            auth_stamp=obj.get("auth_stamp"),
            full_name=full_name,
            license=license_val,
        )

    # ORM or GetterDict: read attributes directly; .get on GetterDict can yield empty for column keys.
    first = str(getattr(obj, "first_name", None) or "").strip()
    last = str(getattr(obj, "last_name", None) or "").strip()
    middle = getattr(obj, "middle_name", None)
    if middle is not None:
        middle = str(middle).strip() or None
    full_name = _format_personnel_account_full_name(last, first, middle)
    if not full_name:
        alt = getattr(obj, "full_name", None)
        if alt is not None and str(alt).strip():
            full_name = str(alt).strip()
    if not full_name:
        full_name = str(getattr(obj, "username", None) or "").strip()

    return AccountInformationPersonnelSummary(
        id=getattr(obj, "id", None),
        designation=getattr(obj, "designation", None),
        auth_stamp=getattr(obj, "auth_stamp", None),
        full_name=full_name,
        license=getattr(obj, "license_no", None),
    )


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
