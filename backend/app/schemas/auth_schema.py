"""Schemas for authentication API."""
from typing import Optional, List
from pydantic import BaseModel


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

    full_name: str
    role: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[str] = None
    username: str
