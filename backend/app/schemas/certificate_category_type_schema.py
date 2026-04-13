from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CertificateCategoryTypeBase(BaseModel):
    name: str = Field(..., description="Category name (TEXT)")

    class Config:
        orm_mode = True


class CertificateCategoryTypeCreate(CertificateCategoryTypeBase):
    pass


class CertificateCategoryTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Category name")

    class Config:
        orm_mode = True


class CertificateCategoryTypeRead(CertificateCategoryTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class CertificateCategoryTypeListItem(BaseModel):
    """For dropdowns / list items."""
    id: int
    name: str

    class Config:
        orm_mode = True
