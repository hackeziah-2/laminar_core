from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuthorizationScopePiperPa34Base(BaseModel):
    name: str = Field(..., description="Authorization scope Piper PA-34 name")

    class Config:
        orm_mode = True


class AuthorizationScopePiperPa34Create(AuthorizationScopePiperPa34Base):
    pass


class AuthorizationScopePiperPa34Update(BaseModel):
    name: Optional[str] = Field(None, description="Authorization scope Piper PA-34 name")

    class Config:
        orm_mode = True


class AuthorizationScopePiperPa34Read(AuthorizationScopePiperPa34Base):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AuthorizationScopePiperPa34ListItem(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
