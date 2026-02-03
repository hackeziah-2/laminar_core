from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class AircraftSummary(BaseModel):
    """Aircraft summary for LDND responses (id, registration)."""

    id: int
    registration: str

    class Config:
        orm_mode = True


class LDNDMonitoringBase(BaseModel):
    aircraft_fk: int
    inspection_type: str = Field(..., max_length=100)
    unit: str = Field(default="HRS", description="HRS or CYCLES")
    last_done_tach_due: Optional[float] = None
    last_done_tach_done: Optional[float] = None
    next_due_tach_hours: Optional[float] = None
    performed_date_start: Optional[date] = None
    performed_date_end: Optional[date] = None

    @validator("unit", pre=True)
    def validate_unit(cls, v):
        if v is None:
            return "HRS"
        u = str(v).upper().strip()
        if u not in ("HRS", "CYCLES"):
            raise ValueError("unit must be HRS or CYCLES")
        return u

    class Config:
        orm_mode = True


class LDNDMonitoringCreate(LDNDMonitoringBase):
    pass


class LDNDMonitoringUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    inspection_type: Optional[str] = Field(None, max_length=100)
    unit: Optional[str] = None
    last_done_tach_due: Optional[float] = None
    last_done_tach_done: Optional[float] = None
    next_due_tach_hours: Optional[float] = None
    performed_date_start: Optional[date] = None
    performed_date_end: Optional[date] = None

    @validator("unit", pre=True)
    def validate_unit(cls, v):
        if v is None:
            return None
        u = str(v).upper().strip()
        if u not in ("HRS", "CYCLES"):
            raise ValueError("unit must be HRS or CYCLES")
        return u

    class Config:
        orm_mode = True


class LDNDMonitoringRead(LDNDMonitoringBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    aircraft: Optional[AircraftSummary] = None

    @validator("unit", pre=True)
    def unit_to_str(cls, v):
        if hasattr(v, "value"):
            return v.value
        return str(v) if v is not None else "HRS"

    class Config:
        orm_mode = True


class LDNDLatestResponse(BaseModel):
    """Maintenance summary: current tach, next inspection, last updated (from latest LDND records for aircraft)."""

    current_tach: Optional[float] = Field(
        None,
        description="Latest current tach (last_done_tach_done from the most recently updated LDND record).",
    )
    next_inspection_tach_hours: Optional[float] = Field(
        None,
        description="Next due tach hours (minimum next_due_tach_hours across records).",
    )
    next_inspection_type: Optional[str] = Field(
        None,
        description="Inspection type of the record with the soonest next due.",
    )
    next_inspection_unit: Optional[str] = Field(
        None,
        description="Unit (HRS/CYCLES) for next inspection.",
    )
    last_updated: Optional[datetime] = Field(
        None,
        description="Most recent updated_at across all LDND records for this aircraft.",
    )

    class Config:
        orm_mode = True
