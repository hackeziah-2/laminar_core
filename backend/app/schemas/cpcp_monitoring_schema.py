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
    aircraft_id: int = Field(..., description="Aircraft ID (required).")
    inspection_operation: str = Field(..., max_length=255)
    description: Optional[str] = None

    interval_hours: Optional[float] = None
    interval_months: Optional[float] = None

    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_date: Optional[date] = None

    atl_ref: Optional[int] = Field(
        None,
        description=(
            "ATL (aircraft_technical_log) ID. Search: GET /api/v1/aircraft-technical-log/search"
            "?search={sequence_no}&aircraft_id={aircraft_id}; use response item `id`. "
            "Show `search_display` in the picker (sequence_no: TACH: … AFTT: … DATE: …)."
        ),
    )

    class Config:
        orm_mode = True


class CPCPMonitoringCreate(CPCPMonitoringBase):
    """Schema for creating a CPCP Monitoring entry."""
    pass


class CPCPMonitoringUpdate(BaseModel):
    """Schema for updating a CPCP Monitoring entry (all fields optional)."""
    aircraft_id: Optional[int] = None
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
    aircraft_id: int
    atl: Optional[AtlRefRead] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    next_due_tach: Optional[float] = Field(
        None,
        description="last_done_tach + interval_hours (stored on create/update).",
    )
    next_due_aftt: Optional[float] = Field(
        None,
        description="last_done_aftt + interval_hours (stored on create/update).",
    )
    next_due_date: Optional[date] = Field(
        None,
        description="last_done_date advanced by interval_months (EDATE-style; stored on create/update).",
    )
    remaining_months: Optional[float] = Field(
        None,
        description="Approx. months from current Asia/Manila date to next_due_date: (end_date - today).days / 365 * 12.",
    )
    remaining_days: Optional[int] = Field(
        None,
        description="Calendar days from current Asia/Manila date to next_due_date: (end_date - today).days (negative if overdue).",
    )
    remaining_tach: Optional[float] = Field(
        None,
        description="next_due_tach minus latest ATL tachometer_end (same source as GET …/aircraft/{id}/details).",
    )
    remaining_aftt: Optional[float] = Field(
        None,
        description="next_due_aftt minus latest ATL airframe_aftt (auto_comp_airframe_aftt from details).",
    )

    class Config:
        orm_mode = True
