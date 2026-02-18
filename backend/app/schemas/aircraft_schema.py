from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, validator


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
    
    # Propeller Information
    propeller_model: Optional[str]
    propeller_serial_number: Optional[str]

    engine_arc: Optional[str] = None
    propeller_arc: Optional[str] = None


class AircraftCreate(AircraftBase):
    class Config:
        orm_mode = True
    

class AircraftUpdate(AircraftBase):
    class Config:
        orm_mode = True

class AircraftOut(AircraftBase):
    id: int
    class Config:
        orm_mode = True



# Example Enum
# class StatusEnum(str, enum.Enum):
#     ACTIVE = "ACTIVE"
#     INACTIVE = "INACTIVE"

# Pydantic schema
class AircraftImportSchema(BaseModel):
    registration: str
    manufacturer: str
    report_description: Optional[str] = None
    type: str
    model: str
    msn: str
    base: str
    ownership: str
    status: AircrarftStatus = AircrarftStatus.active

    airframe_model: Optional[str] = None
    airframe_service_manual: Optional[str] = None
    airframe_serial_number: Optional[str] = None
    airframe_ipc: Optional[str] = None

    engine_model: Optional[str] = None
    engine_serial_number: Optional[str] = None
    engine_arc: Optional[str] = None

    propeller_model: Optional[str] = None
    propeller_serial_number: Optional[str] = None
    propeller_arc: Optional[str] = None

    @validator("status", pre=True)
    def normalize_status(cls, v):
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return AircrarftStatus.active
        if isinstance(v, AircrarftStatus):
            return v
        if isinstance(v, str):
            s = str(v).strip()
            for member in AircrarftStatus:
                if member.value.lower() == s.lower():
                    return member
            return AircrarftStatus.active
        return AircrarftStatus.active

    class Config:
        orm_mode = True