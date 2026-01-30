from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------- Mechanic Detail Schema (for nested mechanic info) ----------
class MechanicDetail(BaseModel):
    """Mechanic details for logbook entries."""
    id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    license_no: Optional[str] = None

    class Config:
        orm_mode = True


# ---------- Engine Logbook Schemas ----------
class EngineLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    engine_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class EngineLogbookCreate(EngineLogbookBase):
    pass


class EngineLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    engine_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class EngineLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    engine_tsn: Optional[float] = None
    sequence_no: str
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- Airframe Logbook Schemas ----------
class AirframeLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class AirframeLogbookCreate(AirframeLogbookBase):
    pass


class AirframeLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class AirframeLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    sequence_no: str
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- Avionics Logbook Schemas ----------
class AvionicsLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    airframe_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    component: Optional[str] = Field(None, max_length=255)
    part_no: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class AvionicsLogbookCreate(AvionicsLogbookBase):
    pass


class AvionicsLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    airframe_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    component: Optional[str] = Field(None, max_length=255)
    part_no: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class AvionicsLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    airframe_tsn: Optional[float] = None
    sequence_no: str
    component: Optional[str] = None
    part_no: Optional[str] = None
    serial_no: Optional[str] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- Propeller Logbook Schemas ----------
class PropellerLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    propeller_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class PropellerLogbookCreate(PropellerLogbookBase):
    pass


class PropellerLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    propeller_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)


class PropellerLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    propeller_tsn: Optional[float] = None
    sequence_no: str
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
