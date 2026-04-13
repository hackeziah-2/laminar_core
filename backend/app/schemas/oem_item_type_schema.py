from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OemItemTypeBase(BaseModel):
    name: str = Field(..., description="OEM item type name")

    class Config:
        orm_mode = True


class OemItemTypeCreate(OemItemTypeBase):
    pass


class OemItemTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, description="OEM item type name")

    class Config:
        orm_mode = True


class OemItemTypeRead(OemItemTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class OemItemTypeListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
