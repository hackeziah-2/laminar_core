"""Schemas for GET /api/v1/dashboard/aircraft-fuel-report (monthly ATL rollup)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, root_validator, validator


def parse_year_month(value: str) -> tuple[int, int]:
    """Parse YYYY-MM → (year, month). Raises ValueError on bad format."""
    text = (value or "").strip()
    parts = text.split("-")
    if len(parts) != 2:
        raise ValueError("must be YYYY-MM")
    year_s, month_s = parts
    if len(year_s) != 4 or not year_s.isdigit() or not month_s.isdigit():
        raise ValueError("must be YYYY-MM")
    year = int(year_s)
    month = int(month_s)
    if month < 1 or month > 12:
        raise ValueError("month must be 01–12")
    if year < 1900 or year > 2100:
        raise ValueError("year out of range")
    return year, month


class AircraftFuelReportQuery(BaseModel):
    """Validated query parameters for the monthly fuel report."""

    start_month: Optional[str] = None
    end_month: Optional[str] = None
    # Normalized uppercase tail numbers (empty = all aircraft)
    aircraft: List[str] = Field(default_factory=list)
    # Optional aircraft PKs (merged with tails when resolving the filter)
    aircraft_ids: List[int] = Field(default_factory=list)
    # Calendar years for YoY flying-hours summary
    # (default: years spanned by start_month..end_month)
    years: List[int] = Field(default_factory=list)
    # Single month slicer for per-aircraft breakdown (YYYY-MM)
    month_year: Optional[str] = None

    @validator("start_month", "end_month", "month_year", pre=True)
    def _empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @validator("start_month", "end_month", "month_year")
    def _validate_ym(cls, v):
        if v is None:
            return None
        parse_year_month(v)
        return v.strip()

    @validator("aircraft_ids", pre=True)
    def _coerce_aircraft_ids(cls, v):
        if v is None:
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        return list(v)

    @validator("years", pre=True)
    def _coerce_years(cls, v):
        if v is None:
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        return list(v)

    @validator("years")
    def _validate_years(cls, v):
        out: List[int] = []
        seen = set()
        for year in v:
            if year < 1900 or year > 2100:
                raise ValueError("year out of range")
            if year not in seen:
                seen.add(year)
                out.append(year)
        return out

    @root_validator
    def _range_order(cls, values):
        start = values.get("start_month")
        end = values.get("end_month")
        if start and end:
            sy, sm = parse_year_month(start)
            ey, em = parse_year_month(end)
            if (sy, sm) > (ey, em):
                raise ValueError("start_month must be <= end_month")
        return values


class FuelReportRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class FuelReportMeta(BaseModel):
    source: str = "ATL Logbook"
    range: FuelReportRange
    generated_at: datetime
    # ATL fuel columns are unitless numerics; product convention is gallons.
    fuel_unit: str = "gallons"


class FuelReportSummary(BaseModel):
    total_hours: float
    total_fuel_gal: float
    avg_fuel_burn_per_hour: Optional[float] = None
    total_oil_usage_qrts: float
    total_landings: int


class AircraftFuelBreakdown(BaseModel):
    tail_number: str
    hours: float
    fuel_gal: float
    fuel_burn_per_hour: Optional[float] = None
    oil_usage_qrts: float


class MonthlyFuelRow(BaseModel):
    month: str
    month_label: str
    hours: float
    fuel_gal: float
    fuel_burn_per_hour: Optional[float] = None
    oil_usage_qrts: float
    landings: int
    aircraft_breakdown: List[AircraftFuelBreakdown] = Field(default_factory=list)


class DataQualityFlag(BaseModel):
    code: str
    message: str
    sequence_no: Optional[str] = None
    aircraft_tail: Optional[str] = None
    origin_date: Optional[str] = None


class YoyFlyingHoursMonth(BaseModel):
    month: str
    values: Dict[str, float]
    flag: Optional[str] = None


class YoyFlyingHours(BaseModel):
    years: List[int]
    months: List[YoyFlyingHoursMonth]
    average_fh: Dict[str, float]
    grand_total: Dict[str, float]


class AircraftMonthBreakdownRow(BaseModel):
    tail_number: str
    hours: float
    fuel: float
    fuel_burn_per_hour: Optional[float] = None
    flag: Optional[str] = None


class AircraftMonthBreakdown(BaseModel):
    month_year: Optional[str] = None
    aircraft: List[AircraftMonthBreakdownRow] = Field(default_factory=list)


class AircraftFuelReportResponse(BaseModel):
    meta: FuelReportMeta
    summary: FuelReportSummary
    monthly: List[MonthlyFuelRow]
    data_quality_flags: List[DataQualityFlag] = Field(default_factory=list)
    yoy_flying_hours: YoyFlyingHours
    aircraft_month_breakdown: AircraftMonthBreakdown
