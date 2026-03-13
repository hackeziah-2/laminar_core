from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class OemItemTypeSummary(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class OemTechnicalPublicationBase(BaseModel):
    item_fk: int
    date_of_expiration: Optional[date] = None

    class Config:
        orm_mode = True


class OemTechnicalPublicationCreate(OemTechnicalPublicationBase):
    pass


class OemTechnicalPublicationUpdate(BaseModel):
    item_fk: Optional[int] = None
    date_of_expiration: Optional[date] = None

    class Config:
        orm_mode = True


class OemTechnicalPublicationRead(OemTechnicalPublicationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item: Optional[OemItemTypeSummary] = None

    class Config:
        orm_mode = True
