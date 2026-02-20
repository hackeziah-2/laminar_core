from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ModuleBase(BaseModel):
    """Base schema for Module."""
    name: str = Field(..., max_length=150)


class ModuleCreate(ModuleBase):
    """Schema for creating Module."""


class ModuleUpdate(BaseModel):
    """Schema for updating Module."""
    name: Optional[str] = Field(None, max_length=150)


class ModuleRead(ModuleBase):
    """Schema for reading Module."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ModuleListItem(BaseModel):
    """Simplified schema for module list (dropdowns)."""
    id: int
    name: str

    class Config:
        orm_mode = True
