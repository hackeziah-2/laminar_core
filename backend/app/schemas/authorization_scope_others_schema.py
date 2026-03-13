from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuthorizationScopeOthersBase(BaseModel):
    name: str = Field(..., description="Authorization scope (others) name")

    class Config:
        orm_mode = True


class AuthorizationScopeOthersCreate(AuthorizationScopeOthersBase):
    pass


class AuthorizationScopeOthersUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Authorization scope (others) name")

    class Config:
        orm_mode = True


class AuthorizationScopeOthersRead(AuthorizationScopeOthersBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AuthorizationScopeOthersListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
