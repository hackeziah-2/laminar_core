from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RolePermissionItem(BaseModel):
    """Permission for a single module (read/write/approve)."""
    module: str = Field(..., description="Module name (e.g. Dashboard, General Information)")
    read: bool = False
    write: bool = False
    approve: bool = False


class RoleBase(BaseModel):
    """Base schema for Role."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating Role."""
    permissions: Optional[List[RolePermissionItem]] = Field(
        default_factory=list,
        description="Optional permissions per module (read, write, approve).",
    )


class RoleUpdate(BaseModel):
    """Schema for updating Role."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    permissions: Optional[List[RolePermissionItem]] = Field(
        None,
        description="Optional: replace role permissions (module, read, write, approve).",
    )


class RoleRead(RoleBase):
    """Schema for reading Role."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class RoleReadWithPermissions(RoleRead):
    """Role with permissions array for each module."""
    permissions: List[RolePermissionItem] = Field(default_factory=list)


class RoleListItem(BaseModel):
    """Simplified schema for role list (dropdowns)."""
    id: int
    name: str
    user_count: int = 0

    class Config:
        orm_mode = True
