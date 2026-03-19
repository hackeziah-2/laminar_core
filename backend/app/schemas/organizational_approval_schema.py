from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class CertificateCategoryTypeSummary(BaseModel):
    """Embedded in OrganizationalApprovalRead."""
    id: int
    name: str

    class Config:
        orm_mode = True


class OrganizationalApprovalBase(BaseModel):
    certificate_fk: int
    number: Optional[str] = Field(None, description="Certificate number (text)")
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)
    is_withhold: bool = False

    class Config:
        orm_mode = True


class OrganizationalApprovalCreate(OrganizationalApprovalBase):
    pass


class OrganizationalApprovalCreateRequestBody(BaseModel):
    """Request body for POST: { \"json_data\": { ... } }."""

    json_data: OrganizationalApprovalCreate


class OrganizationalApprovalUpdate(BaseModel):
    certificate_fk: Optional[int] = None
    number: Optional[str] = None
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)
    is_withhold: Optional[bool] = None

    class Config:
        orm_mode = True


class OrganizationalApprovalUpdateRequestBody(BaseModel):
    """Request body for PUT/PATCH: { \"json_data\": { ... } }."""

    json_data: OrganizationalApprovalUpdate


class OrganizationalApprovalRead(OrganizationalApprovalBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    certificate: Optional[CertificateCategoryTypeSummary] = None

    class Config:
        orm_mode = True
