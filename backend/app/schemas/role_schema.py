from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, root_validator


class RolePermissionItem(BaseModel):
    """Permission for a single module (read, create, update, delete; optional approve)."""
    module: str = Field(..., description="Module name (e.g. Dashboard, General Information)")
    read: bool = Field(False, description="View / list / get")
    create: bool = Field(False, description="Create new records")
    update: bool = Field(False, description="Update existing records")
    delete: bool = Field(False, description="Delete records")
    approve: bool = Field(False, description="Approval workflows where applicable")

    @root_validator(pre=True)
    def _legacy_write_flag(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        write = values.get("write", None)
        has_cud = any(k in values for k in ("create", "update", "delete"))
        if write is not None and not has_cud:
            bv = bool(write)
            values = {**values, "create": bv, "update": bv, "delete": bv}
        values.pop("write", None)
        return values


class RoleBase(BaseModel):
    """Base schema for Role."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating Role."""
    permissions: Optional[List[RolePermissionItem]] = Field(
        default_factory=list,
        description="Optional permissions per module (read, create, update, delete, approve).",
    )


class RoleUpdate(BaseModel):
    """Schema for updating Role."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    permissions: Optional[List[RolePermissionItem]] = Field(
        None,
        description="Optional: replace role permissions (module, read, create, update, delete, approve).",
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
