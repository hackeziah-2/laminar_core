from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.schemas.aircraft_statutory_certificate_schema import CategoryTypeEnum


class AircraftStatutoryCertificateHistoryBase(BaseModel):
    aircraft_fk: int
    category_type: CategoryTypeEnum
    date_of_expiration: Optional[date] = None
    web_link: Optional[str] = Field(None, max_length=2048)

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


class AircraftStatutoryCertificateHistoryCreate(AircraftStatutoryCertificateHistoryBase):
    pass


class AircraftStatutoryCertificateHistoryRead(AircraftStatutoryCertificateHistoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
