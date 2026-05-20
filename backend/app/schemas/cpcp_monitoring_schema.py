import math
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from pydantic.class_validators import validator

from app.services.excel_import.parsers import coerce_import_float, is_spreadsheet_empty, parse_import_date


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


class CPCPMonitoringImportSchema(BaseModel):
    """One spreadsheet row for CPCP monitoring import (aircraft_id from form context)."""

    aircraft_id: int
    inspection_operation: str = Field(..., max_length=255)
    description: Optional[str] = None
    interval_hours: Optional[float] = None
    interval_months: Optional[float] = None
    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_date: Optional[date] = None
    atl_sequence: Optional[str] = Field(
        None,
        description=(
            "ATL sequence_no from spreadsheet (Sequence No./ATL Ref); "
            "on import we load aircraft_technical_log where sequence_no matches and set atl_ref to that row's id."
        ),
    )
    atl_ref: Optional[int] = None

    @validator("inspection_operation", pre=True)
    def coerce_inspection_operation(cls, v: Any) -> str:
        if is_spreadsheet_empty(v):
            raise ValueError("inspection_operation is required")
        return str(v).strip()

    @validator(
        "interval_hours",
        "interval_months",
        "last_done_tach",
        "last_done_aftt",
        pre=True,
    )
    def coerce_optional_floats(cls, v: Any) -> Any:
        return coerce_import_float(v)

    @validator("last_done_date", pre=True)
    def coerce_import_date(cls, v: Any) -> Any:
        if is_spreadsheet_empty(v):
            return None
        parsed = parse_import_date(v)
        if isinstance(parsed, date):
            return parsed
        if is_spreadsheet_empty(parsed):
            return None
        if isinstance(parsed, str):
            raise ValueError(f"invalid date format: {parsed!r}")
        return parsed

    @validator("atl_sequence", pre=True)
    def coerce_atl_sequence(cls, v: Any) -> Any:
        if is_spreadsheet_empty(v):
            return None
        if isinstance(v, float):
            if not math.isfinite(v):
                return None
            if v.is_integer():
                return str(int(v))
            return str(v).strip()
        if isinstance(v, int) and not isinstance(v, bool):
            return str(v)
        s = str(v).strip()
        return s if s and s.upper() not in ("-", "NA", "N/A") else None


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
