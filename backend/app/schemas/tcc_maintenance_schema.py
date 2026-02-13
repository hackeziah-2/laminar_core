from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


# Method of compliance values for API (string)
METHOD_OF_COMPLIANCE_VALUES = [
    "Overhaul", "Replacement", "Inspection", "I&S",
    "Operational Test", "Calibration"
]

# Category values for API (string): Powerplant, Airframe, Inspection Servicing
TCC_CATEGORY_VALUES = ["Powerplant", "Airframe", "Inspection Servicing"]


def _enum_to_str(v):
    """Convert enum to string for API response."""
    if hasattr(v, "value"):
        return v.value
    return str(v) if v is not None else None


# ATL Reference: search by sequence number via GET /api/v1/aircraft-technical-log/search?search={sequence_no}; use returned `id` as atl_ref.
class TCCMaintenanceBase(BaseModel):
    """Base schema for TCC Maintenance."""
    aircraft_fk: int
    atl_ref: Optional[int] = Field(
        None,
        description="ATL (aircraft_technical_log) ID. Search by sequence number: GET /api/v1/aircraft-technical-log/search?search={sequence_no}. Use response item id as atl_ref.",
    )
    category: Optional[str] = Field(None, max_length=50, description="Powerplant, Airframe, Inspection Servicing")
    part_number: str = Field(..., max_length=255)
    serial_number: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    component_limit_years: Optional[int] = None
    component_limit_hours: Optional[float] = None
    component_method_of_compliance: Optional[str] = Field(None, max_length=50)

    last_done_date: Optional[date] = None
    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_method_of_compliance: Optional[str] = Field(None, max_length=50)

    @validator("category", "component_method_of_compliance", "last_done_method_of_compliance", pre=True)
    def enum_fields_to_str(cls, v):
        return _enum_to_str(v)

    class Config:
        orm_mode = True


class TCCMaintenanceCreate(TCCMaintenanceBase):
    """Schema for creating a TCC Maintenance entry."""
    pass


class TCCMaintenanceUpdate(BaseModel):
    """Schema for updating a TCC Maintenance entry (all fields optional)."""
    aircraft_fk: Optional[int] = None
    atl_ref: Optional[int] = Field(
        None,
        description="ATL (aircraft_technical_log) ID. Search: GET /api/v1/aircraft-technical-log/search?search={sequence_no}; use response item id.",
    )
    category: Optional[str] = Field(None, max_length=50)
    part_number: Optional[str] = Field(None, max_length=255)
    serial_number: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    component_limit_years: Optional[int] = None
    component_limit_hours: Optional[float] = None
    component_method_of_compliance: Optional[str] = Field(None, max_length=50)

    last_done_date: Optional[date] = None
    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_method_of_compliance: Optional[str] = Field(None, max_length=50)

    @validator("category", "component_method_of_compliance", "last_done_method_of_compliance", pre=True)
    def enum_fields_to_str(cls, v):
        return _enum_to_str(v)

    class Config:
        orm_mode = True



class AircraftTechinicalLogRead(BaseModel):
    aircraft_fk: int
    sequence_no: str = Field(..., max_length=50)

    class Config:
        orm_mode = True

class TCCMaintenanceRead(TCCMaintenanceBase):
    """Schema for reading a TCC Maintenance entry."""
    id: int
    atl: Optional[AircraftTechinicalLogRead] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
