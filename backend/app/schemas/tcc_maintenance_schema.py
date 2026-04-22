import math
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, root_validator, validator


# Method of compliance values for API (string)
METHOD_OF_COMPLIANCE_VALUES = [
    "Overhaul", "Replacement", "Inspection", "I&S",
    "Operational Test", "Calibration"
]

# Category values for API (string): Powerplant, Airframe, Inspection Servicing
TCC_CATEGORY_VALUES = ["All Categories", "All", "Powerplant", "Airframe", "Inspection Servicing"]


def _enum_to_str(v):
    """Convert enum to string for API response."""
    if hasattr(v, "value"):
        return v.value
    return str(v) if v is not None else None


# All optional floats on TCC maintenance API responses: null / missing → 0.0
_TCC_MAINTENANCE_API_FLOAT_FIELDS = (
    "component_limit_years",
    "component_limit_hours",
    "last_done_tach",
    "last_done_aftt",
    "remaining_years",
    "remaining_days",
    "remaining_tach",
    "remaining_aftt",
    "next_due_tach",
    "next_due_aftt",
)


def _float_api_default_zero(v) -> float:
    """Coerce null or non-finite floats to 0.0 for JSON responses."""
    if v is None:
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


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

    component_limit_years: Optional[float] = None
    component_limit_hours: Optional[float] = None
    component_method_of_compliance: Optional[str] = Field(None, max_length=50)

    last_done_date: Optional[date] = None
    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_method_of_compliance: Optional[str] = Field(None, max_length=50)

    remaining_years: Optional[float] = Field(
        None,
        description="Computed on save (2 decimal places): days until next_due_date ÷ 365 when next_due_date is set; may be negative if overdue. Optional explicit value on create overrides computed.",
    )
    remaining_days: Optional[float] = Field(
        None,
        description="Computed on save: calendar days from current date to next_due_date (negative if overdue). Optional explicit value on create overrides computed.",
    )
    remaining_tach: Optional[float] = Field(
        None,
        description=(
            "Computed on save: next_due_tach − tachometer_end from the latest ATL (by sequence_no); "
            "may be negative if overdue. Optional explicit value on create overrides computed. "
            "Read responses round to 1 decimal place."
        ),
    )
    remaining_aftt: Optional[float] = Field(
        None,
        description=(
            "Computed on save: next_due_aftt (from this row after save) minus cumulative airframe AFTT "
            "from the latest ATL by sequence_no, using the same auto_comp_airframe_aftt rule as "
            "GET /api/v1/aircraft/{id}/details/; may be negative if overdue."
        ),
    )

    next_due_date: Optional[date] = Field(
        None,
        description="Computed on save: last_done_date + whole limit years + fractional years in days.",
    )
    next_due_tach: Optional[float] = Field(
        None,
        description="Computed on save: last_done_tach + limit_hours when both are set.",
    )
    next_due_aftt: Optional[float] = Field(
        None,
        description="Computed on save: last_done_aftt + limit_hours when both are set.",
    )

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

    component_limit_years: Optional[float] = None
    component_limit_hours: Optional[float] = None
    component_method_of_compliance: Optional[str] = Field(None, max_length=50)

    last_done_date: Optional[date] = None
    last_done_tach: Optional[float] = None
    last_done_aftt: Optional[float] = None
    last_done_method_of_compliance: Optional[str] = Field(None, max_length=50)

    remaining_years: Optional[float] = None
    remaining_days: Optional[float] = None
    remaining_tach: Optional[float] = None
    remaining_aftt: Optional[float] = None

    next_due_date: Optional[date] = None
    next_due_tach: Optional[float] = None
    next_due_aftt: Optional[float] = None

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

    @root_validator(pre=False)
    def null_floats_to_zero(cls, values):
        for key in _TCC_MAINTENANCE_API_FLOAT_FIELDS:
            values[key] = _float_api_default_zero(values.get(key))
        values["remaining_tach"] = round(values["remaining_tach"], 1)
        return values

    class Config:
        orm_mode = True


class TCCMaintenancePagedResponse(BaseModel):
    """Response for GET /api/v1/tcc-maintenance/paged and GET /api/v1/aircraft/{aircraft_id}/tcc-maintenance/paged."""

    items: List[TCCMaintenanceRead] = Field(default_factory=list)
    total: int = Field(..., description="Total matching rows (not just this page)")
    page: int = Field(..., description="Current page (1-based)")
    pages: int = Field(..., description="Total pages for this page size")

    class Config:
        orm_mode = False
