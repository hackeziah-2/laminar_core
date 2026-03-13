from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuthorizationScopeCessnaBase(BaseModel):
    name: str = Field(..., description="Authorization scope Cessna name")

    class Config:
        orm_mode = True


class AuthorizationScopeCessnaCreate(AuthorizationScopeCessnaBase):
    pass


class AuthorizationScopeCessnaUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Authorization scope Cessna name")

    class Config:
        orm_mode = True


class AuthorizationScopeCessnaRead(AuthorizationScopeCessnaBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AuthorizationScopeCessnaListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
