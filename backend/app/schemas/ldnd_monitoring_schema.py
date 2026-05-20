from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, validator

from app.services.excel_import.parsers import parse_import_date


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


def _coerce_optional_float(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s or s in ("-", "NA", "N/A"):
            return None
        try:
            return float(s)
        except ValueError:
            return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return v


class LDNDMonitoringImportSchema(BaseModel):
    """One spreadsheet row for LDND monitoring import (aircraft_fk from form context)."""

    aircraft_fk: int
    inspection_type: str = Field(..., max_length=100)
    unit: str = Field(default="HRS")
    last_done_tach_due: Optional[float] = None
    last_done_tach_done: Optional[float] = None
    next_due_tach_hours: Optional[float] = None
    performed_date_start: Optional[date] = None
    performed_date_end: Optional[date] = None

    @validator("inspection_type", pre=True)
    def coerce_inspection_type(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("inspection_type is required")
        return str(v).strip()

    @validator("unit", pre=True)
    def validate_unit(cls, v: Any) -> str:
        if v is None:
            return "HRS"
        u = str(v).upper().strip()
        if u not in ("HRS", "CYCLES"):
            raise ValueError("unit must be HRS or CYCLES")
        return u

    @validator(
        "last_done_tach_due",
        "last_done_tach_done",
        "next_due_tach_hours",
        pre=True,
    )
    def coerce_optional_floats(cls, v: Any) -> Any:
        return _coerce_optional_float(v)

    @validator("last_done_tach_done", pre=False)
    def require_last_done_tach_done(cls, v: Any) -> float:
        if v is None:
            raise ValueError("last_done_tach_done is required for import upsert")
        return v

    @validator("performed_date_start", "performed_date_end", pre=True)
    def coerce_import_dates(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        parsed = parse_import_date(v)
        if isinstance(parsed, date):
            return parsed
        if isinstance(parsed, str):
            raise ValueError(f"invalid date format: {parsed!r}")
        return parsed


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


class LDNDInspectionTypeLatestResponse(BaseModel):
    """Latest LDND row for an aircraft where tach and performed-date fields are all unset (placeholder / not-yet-filled row)."""

    inspection_type: str = ""
    unit: str = ""

    class Config:
        orm_mode = True


class LDNDLatestResponse(BaseModel):
    """Maintenance summary: current tach, next inspection, last updated, and latest record details (from the latest performed LDND record for aircraft)."""

    current_tach: Optional[float] = Field(
        None,
        description="Latest current tach (last_done_tach_done from the LDND record with the newest performed_date_start).",
    )
    next_inspection_tach_hours: Optional[float] = Field(
        None,
        description="Next due tach hours (minimum next_due_tach_hours across records).",
    )
    next_inspection_due: Optional[float] = Field(
        None,
        description="Next inspection due (numeric tach value) for the record with the soonest next due.",
    )
    next_inspection_unit: Optional[str] = Field(
        None,
        description="Unit (HRS/CYCLES) for next inspection.",
    )
    last_updated: Optional[datetime] = Field(
        None,
        description="updated_at (or created_at) of the LDND record with the newest performed_date_start.",
    )
    lastest_inspection: Optional[str] = Field(
        None,
        description="Inspection type from the latest created LDND monitoring entry.",
    )
    # Latest record fields
    inspection_type: Optional[str] = Field(None, description="Inspection type from latest record.")
    unit: Optional[str] = Field(None, description="Unit (HRS/CYCLES) from latest record.")
    last_done_tach_due: Optional[float] = Field(None, description="Last done tach due from latest record.")
    last_done_tach_done: Optional[float] = Field(None, description="Last done tach done from latest record.")
    next_due_tach_hours: Optional[float] = Field(None, description="Next due tach hours from latest record.")
    performed_date_start: Optional[date] = Field(None, description="Performed date start from latest record.")
    performed_date_end: Optional[date] = Field(None, description="Performed date end from latest record.")
    aircraft: Optional[AircraftSummary] = Field(None, description="Aircraft (id, registration) for the latest record.")

    class Config:
        orm_mode = True
