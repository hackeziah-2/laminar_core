from pydantic import BaseModel
from datetime import datetime
from typing import Optional
class FlightBase(BaseModel):
    flight_no: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    # status: Optional[str] = "scheduled"

class FlightCreate(FlightBase):
    pass

class FlightUpdate(BaseModel):
    flight_no: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    departure_time: Optional[datetime]
    arrival_time: Optional[datetime]
    status: Optional[str]

class FlightOut(FlightBase):
    id: int
    class Config:
        orm_mode = True
