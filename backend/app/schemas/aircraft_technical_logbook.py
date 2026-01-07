from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Base ----------
class AircraftLogbookEntryBase(BaseModel):
    aircraft_id: int

    sequence_no: str = Field(..., max_length=50)
    nature_of_flight: Optional[str] = Field(None, max_length=50)
    nature_others: Optional[str] = Field(None, max_length=100)

    # Off / On blocks
    off_blocks_station: str = Field(..., max_length=10)
    off_blocks_date: date
    off_blocks_time: time

    on_blocks_station: str = Field(..., max_length=10)
    on_blocks_date: date
    on_blocks_time: time

    total_flight_time: float

    # Tach / Hobbs
    tach_start: float
    tach_end: float
    tach_total: float

    hobbs_start: float
    hobbs_end: float
    hobbs_total: float

    # Notes
    pilot_report: Optional[str] = None
    maintenance_entry: Optional[str] = None
    actions_taken: Optional[str] = None

    # Component times
    airframe_time: float
    engine_time: float
    propeller_time: float


# ---------- Create ----------
class AircraftLogbookEntryCreate(AircraftLogbookEntryBase):
    pass


# ---------- Update ----------
class AircraftLogbookEntryUpdate(BaseModel):
    nature_of_flight: Optional[str] = Field(None, max_length=50)
    nature_others: Optional[str] = Field(None, max_length=100)

    off_blocks_station: Optional[str] = Field(None, max_length=10)
    off_blocks_date: Optional[date]
    off_blocks_time: Optional[time]

    on_blocks_station: Optional[str] = Field(None, max_length=10)
    on_blocks_date: Optional[date]
    on_blocks_time: Optional[time]

    total_flight_time: Optional[float]

    tach_start: Optional[float]
    tach_end: Optional[float]
    tach_total: Optional[float]

    hobbs_start: Optional[float]
    hobbs_end: Optional[float]
    hobbs_total: Optional[float]

    pilot_report: Optional[str]
    maintenance_entry: Optional[str]
    actions_taken: Optional[str]

    airframe_time: Optional[float]
    engine_time: Optional[float]
    propeller_time: Optional[float]


class AircraftRead(BaseModel):
    id: int
    registration: str

    class Config:
        orm_mode = True

# ---------- Read / Response ----------
class AircraftLogbookEntryRead(AircraftLogbookEntryBase):
    id: int
    aircraft: AircraftRead

    class Config:
        orm_mode = True
    