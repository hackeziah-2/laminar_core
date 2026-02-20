from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------- Account Information Base Schema ----------
class AccountInformationBase(BaseModel):
    """Base schema for Account Information."""
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    username: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    designation: Optional[str] = Field(None, max_length=100)
    license_no: Optional[str] = Field(None, max_length=100)
    auth_stamp: Optional[str] = Field(None, max_length=255)
    role_id: Optional[int] = Field(None, description="FK to roles")
    status: bool = Field(True, description="True for active, False for inactive")


# ---------- Account Information Create Schema ----------
class AccountInformationCreate(AccountInformationBase):
    """Schema for creating Account Information."""
    password: str = Field(..., min_length=6, max_length=72, description="Password must be 6-72 characters (bcrypt limit)")


# ---------- Account Information Update Schema ----------
class AccountInformationUpdate(BaseModel):
    """Schema for updating Account Information."""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    password: Optional[str] = Field(None, min_length=6, max_length=72, description="Password must be 6-72 characters (bcrypt limit)")
    designation: Optional[str] = Field(None, max_length=100)
    license_no: Optional[str] = Field(None, max_length=100)
    auth_stamp: Optional[str] = Field(None, max_length=255)
    role_id: Optional[int] = Field(None, description="FK to roles")
    status: Optional[bool] = Field(None, description="True for active, False for inactive")


# ---------- Account Information Read Schema ----------
class AccountInformationRead(AccountInformationBase):
    """Schema for reading Account Information."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    # Password is excluded for security - never return it in responses

    class Config:
        orm_mode = True


# ---------- Account Information List Schema (Simplified) ----------
class AccountInformationListItem(BaseModel):
    """Simplified schema for account information list with fullname and license_no."""
    id: int
    fullname: str
    license_no: Optional[str] = None

    @classmethod
    def from_orm_with_fullname(cls, obj):
        """Create from ORM object with computed fullname."""
        # Build fullname: first_name + middle_name (if exists) + last_name
        fullname_parts = [obj.first_name]
        if obj.middle_name:
            fullname_parts.append(obj.middle_name)
        fullname_parts.append(obj.last_name)
        fullname = " ".join(fullname_parts)
        
        return cls(
            id=obj.id,
            fullname=fullname,
            license_no=obj.license_no
        )

    class Config:
        orm_mode = True
