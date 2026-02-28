from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, validator, root_validator

# Extensions treated as images (for modal preview in Aircraft Details)
_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"})


class AircrarftStatus(str, Enum):
    active = "Active"
    inactive = "Inactive"
    maintenance = "Maintenance"

class AircraftBase(BaseModel):
    registration: Optional[str] = None
    manufacturer: Optional[str] = None
    report_description: Optional[str] = None

    model: Optional[str] = None
    msn: Optional[str] = None
    base: Optional[str] = None
    ownership: Optional[str] = None
    status: Optional[str] = "Active"

    # Airframe Information
    airframe_service_manual: Optional[str]
    airframe_ipc: Optional[str]
    
    # Engine Information
    engine_model: Optional[str]
    engine_serial_number: Optional[str]
    engine_life_time_limit: Optional[float] = None
    
    # Propeller Information
    propeller_model: Optional[str]
    propeller_serial_number: Optional[str]
    propeller_life_time_limit: Optional[float] = None

    engine_arc: Optional[str] = None
    propeller_arc: Optional[str] = None


class AircraftCreate(AircraftBase):
    """Schema for creating an aircraft. Required fields match DB NOT NULL columns."""

    registration: str
    manufacturer: str
    model: str
    msn: str
    base: str
    ownership: str
    status: str = "Active"

    class Config:
        orm_mode = True
    

class AircraftUpdate(AircraftBase):
    class Config:
        orm_mode = True

class AircraftOut(AircraftBase):
    id: int
    # For Aircraft Details: download button and modal view when image
    engine_arc_download_url: Optional[str] = None
    propeller_arc_download_url: Optional[str] = None
    engine_arc_is_image: Optional[bool] = None
    propeller_arc_is_image: Optional[bool] = None

    @root_validator(pre=True)
    def inject_download_urls_and_is_image(cls, v: Any) -> Any:
        if not hasattr(v, "id"):
            return v
        # Build dict from ORM for Pydantic; add download URLs and is_image hints
        base_keys = [
            "id", "registration", "manufacturer", "report_description", "model", "msn",
            "base", "ownership", "status", "airframe_service_manual", "airframe_ipc",
            "engine_model", "engine_serial_number", "engine_life_time_limit",
            "propeller_model", "propeller_serial_number", "propeller_life_time_limit",
            "engine_arc", "propeller_arc",
        ]
        d = {k: getattr(v, k, None) for k in base_keys if hasattr(v, k)}
        aid = getattr(v, "id", None)
        engine_arc = getattr(v, "engine_arc", None)
        propeller_arc = getattr(v, "propeller_arc", None)
        d["engine_arc_download_url"] = f"/api/v1/aircraft/{aid}/files/engine-arc" if engine_arc else None
        d["propeller_arc_download_url"] = f"/api/v1/aircraft/{aid}/files/propeller-arc" if propeller_arc else None
        d["engine_arc_is_image"] = Path(engine_arc).suffix.lower() in _IMAGE_EXTENSIONS if engine_arc else False
        d["propeller_arc_is_image"] = Path(propeller_arc).suffix.lower() in _IMAGE_EXTENSIONS if propeller_arc else False
        return d

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
    model: str
    msn: str
    base: str
    ownership: str
    status: AircrarftStatus = AircrarftStatus.active

    airframe_service_manual: Optional[str] = None
    airframe_ipc: Optional[str] = None

    engine_model: Optional[str] = None
    engine_serial_number: Optional[str] = None
    engine_arc: Optional[str] = None
    engine_life_time_limit: Optional[float] = None

    propeller_model: Optional[str] = None
    propeller_serial_number: Optional[str] = None
    propeller_arc: Optional[str] = None
    propeller_life_time_limit: Optional[float] = None

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