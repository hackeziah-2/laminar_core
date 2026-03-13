from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuthorizationScopeBaronBase(BaseModel):
    name: str = Field(..., description="Authorization scope Baron name")

    class Config:
        orm_mode = True


class AuthorizationScopeBaronCreate(AuthorizationScopeBaronBase):
    pass


class AuthorizationScopeBaronUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Authorization scope Baron name")

    class Config:
        orm_mode = True


class AuthorizationScopeBaronRead(AuthorizationScopeBaronBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AuthorizationScopeBaronListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
