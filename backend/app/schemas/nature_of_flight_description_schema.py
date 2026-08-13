from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.models.aircraft_techinical_log import TypeEnum


class AircraftSummary(BaseModel):
    id: int
    registration: str
    msn: str
    model: str

    class Config:
        orm_mode = True


def _nature_of_flight_to_enum(v):
    if v is None:
        return v
    if isinstance(v, TypeEnum):
        return v
    if hasattr(v, "value"):
        return TypeEnum(v.value) if isinstance(v.value, str) else v
    if isinstance(v, str):
        key = v.strip().upper().replace(" ", "_")
        if key in TypeEnum.__members__:
            return TypeEnum[key]
        if key in [e.value for e in TypeEnum]:
            return TypeEnum(key)
    return v


class NatureOfFlightDescriptionBase(BaseModel):
    aircraft_fk: int = Field(..., description="Aircraft ID")
    nature_of_flight: TypeEnum = Field(..., description="Nature of flight (TypeEnum)")
    remarks: Optional[str] = None
    action_taken: Optional[str] = None

    @validator("nature_of_flight", pre=True)
    def nature_of_flight_to_enum(cls, v):
        return _nature_of_flight_to_enum(v)

    class Config:
        orm_mode = True
        use_enum_values = True


class NatureOfFlightDescriptionCreate(NatureOfFlightDescriptionBase):
    pass


class NatureOfFlightDescriptionAircraftCreate(BaseModel):
    """Create payload for aircraft-scoped routes (aircraft_fk comes from the path)."""
    nature_of_flight: TypeEnum = Field(..., description="Nature of flight (TypeEnum)")
    remarks: Optional[str] = None
    action_taken: Optional[str] = None

    @validator("nature_of_flight", pre=True)
    def nature_of_flight_to_enum(cls, v):
        return _nature_of_flight_to_enum(v)

    class Config:
        orm_mode = True
        use_enum_values = True


class NatureOfFlightDescriptionUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    nature_of_flight: Optional[TypeEnum] = None
    remarks: Optional[str] = None
    action_taken: Optional[str] = None

    @validator("nature_of_flight", pre=True)
    def nature_of_flight_to_enum(cls, v):
        if v is None or v == "":
            return None
        return _nature_of_flight_to_enum(v)

    class Config:
        orm_mode = True
        use_enum_values = True


class NatureOfFlightDescriptionRead(NatureOfFlightDescriptionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    aircraft: Optional[AircraftSummary] = None

    class Config:
        orm_mode = True
        use_enum_values = True


class NatureOfFlightDescriptionLookupRead(BaseModel):
    remarks: Optional[str] = None
    action_taken: Optional[str] = None

    class Config:
        orm_mode = True
