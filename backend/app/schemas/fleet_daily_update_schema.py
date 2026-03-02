from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


FLEET_DAILY_UPDATE_STATUS_VALUES = ["Running", "Ongoing Maintenance", "AOG"]


class AircraftRef(BaseModel):
    """Aircraft reference in fleet daily update response."""
    id: int
    registration: str

    class Config:
        orm_mode = True


def _status_to_str(v):
    if hasattr(v, "value"):
        return v.value
    return str(v) if v is not None else None


class FleetDailyUpdateBase(BaseModel):
    """Base schema for Fleet Daily Update."""
    aircraft_fk: int = Field(..., description="Aircraft ID (one-to-one)")
    created_by: Optional[int] = Field(None, description="User ID who created the record")
    updated_by: Optional[int] = Field(None, description="User ID who last updated the record")
    status: Optional[str] = Field(
        "Running",
        description="Running, Ongoing Maintenance, AOG",
    )
    next_insp_due: Optional[float] = None
    tach_time_due: Optional[float] = None
    tach_time_eod: Optional[float] = None
    remaining_time_before_next_isp: Optional[float] = None
    remaining_time_before_engine: Optional[float] = None
    remaining_time_before_propeller: Optional[float] = None
    remarks: Optional[str] = None

    @validator("status", pre=True)
    def status_to_str(cls, v):
        return _status_to_str(v)

    class Config:
        orm_mode = True


class FleetDailyUpdateCreate(FleetDailyUpdateBase):
    """Schema for creating a Fleet Daily Update entry."""
    created_by: Optional[int] = Field(None, description="User ID who created the record (optional)")


class FleetDailyUpdateUpdate(BaseModel):
    """Schema for updating a Fleet Daily Update entry (all fields optional). Partial update: only send status and/or remarks to update those."""
    aircraft_fk: Optional[int] = None
    updated_by: Optional[int] = Field(None, description="User ID who performed the update")
    status: Optional[str] = Field(None, description="Running, Ongoing Maintenance, AOG")
    next_insp_due: Optional[float] = None
    tach_time_due: Optional[float] = None
    tach_time_eod: Optional[float] = None
    remaining_time_before_next_isp: Optional[float] = None
    remaining_time_before_engine: Optional[float] = None
    remaining_time_before_propeller: Optional[float] = None
    remarks: Optional[str] = Field(None, description="Remarks (can be empty string to clear)")

    @validator("status", pre=True)
    def status_to_str(cls, v):
        if v is None:
            return None
        s = _status_to_str(v)
        if s:
            return s
        # Normalize common variants (case-insensitive)
        if isinstance(v, str):
            vn = v.strip().lower()
            for val in FLEET_DAILY_UPDATE_STATUS_VALUES:
                if val.lower() == vn:
                    return val
        return v

    class Config:
        orm_mode = True


class FleetDailyUpdateRead(FleetDailyUpdateBase):
    """Schema for reading a Fleet Daily Update entry."""
    id: int
    aircraft: Optional[AircraftRef] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
