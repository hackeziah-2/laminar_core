"""Schemas for authentication API."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Login response with token and account info."""
    access_token: str
    token_type: str = "bearer"
    account_id: int
    username: str
    email: Optional[str] = None
    role_id: Optional[int] = None
    full_name: str


class AccountMe(BaseModel):
    """Current account info (for /me endpoint)."""
    id: int
    username: str
    email: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    role_id: Optional[int] = None
    status: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
