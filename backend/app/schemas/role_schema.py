from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    """Base schema for Role."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating Role."""


class RoleUpdate(BaseModel):
    """Schema for updating Role."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class RoleRead(RoleBase):
    """Schema for reading Role."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class RoleListItem(BaseModel):
    """Simplified schema for role list (dropdowns)."""
    id: int
    name: str

    class Config:
        orm_mode = True
