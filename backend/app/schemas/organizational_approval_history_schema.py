from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrganizationalApprovalHistoryBase(BaseModel):
    certificate_fk: int
    number: Optional[str] = None
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)

    class Config:
        orm_mode = True


class OrganizationalApprovalHistoryCreate(OrganizationalApprovalHistoryBase):
    pass


class OrganizationalApprovalHistoryRead(OrganizationalApprovalHistoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
