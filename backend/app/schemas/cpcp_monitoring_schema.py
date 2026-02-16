from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class AtlRefRead(BaseModel):
    """Minimal ATL reference for display (id, sequence_no)."""
    id: int
    sequence_no: str

    class Config:
        orm_mode = True


class CPCPMonitoringBase(BaseModel):
    """Base schema for CPCP Monitoring."""
    inspection_operation: str = Field(..., max_length=255)
    description: Optional[str] = None

    interval_hours: Optional[float] = None
    interval_months: Optional[float] = None

    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_date: Optional[date] = None

    atl_ref: Optional[int] = Field(
        None,
        description="ATL (aircraft_technical_log) ID. Search: GET /api/v1/aircraft-technical-log/search?search={sequence_no}; use response item id.",
    )

    class Config:
        orm_mode = True


class CPCPMonitoringCreate(CPCPMonitoringBase):
    """Schema for creating a CPCP Monitoring entry."""
    pass


class CPCPMonitoringUpdate(BaseModel):
    """Schema for updating a CPCP Monitoring entry (all fields optional)."""
    inspection_operation: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    interval_hours: Optional[float] = None
    interval_months: Optional[float] = None

    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_date: Optional[date] = None

    atl_ref: Optional[int] = None

    class Config:
        orm_mode = True


class CPCPMonitoringRead(CPCPMonitoringBase):
    """Schema for reading a CPCP Monitoring entry."""
    id: int
    atl: Optional[AtlRefRead] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
