import enum
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class CategoryTypeEnum(str, enum.Enum):
    COA = "COA"
    COR = "COR"
    NTC = "NTC"
    PITOT_STATIC = "PITOT_STATIC"
    TRANSPONDER = "TRANSPONDER"
    ELT = "ELT"
    WEIGHT_BALANCE = "WEIGHT_BALANCE"
    COMPASS_SWING = "COMPASS_SWING"
    MARKING_RESERVATION = "MARKING_RESERVATION"
    BINARY_CODE_24BIT = "BINARY_CODE_24BIT"
    IBRD_CORPAS = "IBRD_CORPAS"


class AircraftSummary(BaseModel):
    id: int
    registration: str
    msn: str
    model: str

    class Config:
        orm_mode = True


class AircraftStatutoryCertificateBase(BaseModel):
    aircraft_fk: int
    category_type: CategoryTypeEnum
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)
    file_path: Optional[str] = Field(None, max_length=500)

    @validator("category_type", pre=True)
    def category_type_to_enum(cls, v):
        if v is None:
            return v
        if hasattr(v, "value"):
            return CategoryTypeEnum(v.value) if isinstance(v.value, str) else v
        if isinstance(v, str) and v in [e.value for e in CategoryTypeEnum]:
            return CategoryTypeEnum(v)
        return v

    class Config:
        orm_mode = True


class AircraftStatutoryCertificateCreate(AircraftStatutoryCertificateBase):
    pass


class AircraftStatutoryCertificateUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    category_type: Optional[CategoryTypeEnum] = None
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)
    file_path: Optional[str] = Field(None, max_length=500)

    @validator("category_type", pre=True)
    def category_type_to_enum(cls, v):
        if v is None:
            return v
        if hasattr(v, "value"):
            return CategoryTypeEnum(v.value) if isinstance(v.value, str) else v
        if isinstance(v, str) and v in [e.value for e in CategoryTypeEnum]:
            return CategoryTypeEnum(v)
        return v

    class Config:
        orm_mode = True


class AircraftStatutoryCertificateRead(AircraftStatutoryCertificateBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    aircraft: Optional[AircraftSummary] = None

    class Config:
        orm_mode = True
