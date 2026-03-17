import enum
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class OemTechnicalPublicationCategoryTypeEnum(str, enum.Enum):
    CERTIFICATE = "CERTIFICATE"
    SUBSCRIPTION = "SUBSCRIPTION"
    REGULATORY_CORRESPONDENCE_NON_CERT = "REGULATORY_CORRESPONDENCE_NON_CERT"
    LICENSE = "LICENSE"


class OemItemTypeSummary(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class OemTechnicalPublicationBase(BaseModel):
    item_fk: int
    category_type: OemTechnicalPublicationCategoryTypeEnum
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)

    @validator("category_type", pre=True)
    def category_type_to_enum(cls, v):
        if v is None:
            return v
        if hasattr(v, "value"):
            return OemTechnicalPublicationCategoryTypeEnum(v.value) if isinstance(v.value, str) else v
        if isinstance(v, str) and v in [e.value for e in OemTechnicalPublicationCategoryTypeEnum]:
            return OemTechnicalPublicationCategoryTypeEnum(v)
        return v

    class Config:
        orm_mode = True


class OemTechnicalPublicationCreate(OemTechnicalPublicationBase):
    pass


class OemTechnicalPublicationUpdate(BaseModel):
    item_fk: Optional[int] = None
    category_type: Optional[OemTechnicalPublicationCategoryTypeEnum] = None
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)

    @validator("category_type", pre=True)
    def category_type_to_enum(cls, v):
        if v is None:
            return v
        if hasattr(v, "value"):
            return OemTechnicalPublicationCategoryTypeEnum(v.value) if isinstance(v.value, str) else v
        if isinstance(v, str) and v in [e.value for e in OemTechnicalPublicationCategoryTypeEnum]:
            return OemTechnicalPublicationCategoryTypeEnum(v)
        return v

    class Config:
        orm_mode = True


class OemTechnicalPublicationRead(OemTechnicalPublicationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item: Optional[OemItemTypeSummary] = None

    class Config:
        orm_mode = True
        use_enum_values = True


class OemTechnicalPublicationPagedResponse(BaseModel):
    """Response shape for GET /paged."""

    items: List[OemTechnicalPublicationRead]
    total: int
    page: int
    pages: int
