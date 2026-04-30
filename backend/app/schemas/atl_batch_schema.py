from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AtlBatchBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None

    class Config:
        orm_mode = True


class AtlBatchCreate(AtlBatchBase):
    pass


class AtlBatchUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    class Config:
        orm_mode = True


class AtlBatchRead(AtlBatchBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AtlBatchBrief(BaseModel):
    """Nested on AircraftTechnicalLog read responses."""

    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True


class AtlBatchListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
