from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class AccountInformationNameSummary(BaseModel):
    id: int
    first_name: str
    last_name: str

    class Config:
        orm_mode = True


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


class PersonnelAuthorizationRead(PersonnelAuthorizationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    account_information: Optional[AccountInformationNameSummary] = None
    authorization_scope_cessna: Optional[AuthorizationScopeCessnaSummary] = None
    authorization_scope_baron: Optional[AuthorizationScopeBaronSummary] = None
    authorization_scope_others: Optional[AuthorizationScopeOthersSummary] = None

    class Config:
        orm_mode = True
