
from sqlalchemy import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AircrarftStatus(str, Enum):
    active = "Active"
    inactive = "Inactive"
    maintenance = "Maintenance"

class AircraftBase(BaseModel):
    registration: Optional[str]
    manufacturer: Optional[str]
    report_description: Optional[str]

    type: Optional[str]
    model: Optional[str]
    msn : Optional[str]
    reg_no: Optional[str]
    base: Optional[str]
    ownership : Optional[str]
    status: Optional[str] = "Active"

    # Airframe Information
    airframe_model: Optional[str]
    airframe_service_manual: Optional[str]
    airframe_serial_number: Optional[str]
    airframe_ipc: Optional[str]
    
    # Engine Information
    engine_model: Optional[str]
    engine_serial_number: Optional[str]
    engine_arc: Optional[str]
    
    # Propeller Information
    propeller_model: Optional[str]
    propeller_serial_number: Optional[str]
    propeller_arc: Optional[str]


class AircraftCreate(AircraftBase):
    pass

class AircraftUpdate(AircraftBase):
    class Config:
        orm_mode = True

class AircraftOut(AircraftBase):
    id: int
    class Config:
        orm_mode = True
