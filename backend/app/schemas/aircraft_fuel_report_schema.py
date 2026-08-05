"""Schemas for the Aircraft Fuel Consumption Dashboard report."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, root_validator, validator


class FuelReportPeriod(str, Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class AircraftFuelReportFilters(BaseModel):
    year: int
    month: Optional[int] = None
    week: Optional[int] = None
    aircraft_id: Optional[int] = None
    start_date: date
    end_date: date


class ChartSeries(BaseModel):
    key: str
    name: str
    chart_type: Literal["bar", "line"]
    unit: str
    y_axis: Literal["left", "right"]
    data: List[Optional[float]]


class AircraftFuelMetrics(BaseModel):
    aircraft_id: int
    aircraft_registration: str
    total_flight_hours: float
    left_fuel_gallons: float
    right_fuel_gallons: float
    total_fuel_gallons: float
    total_oil_quarts: float
    fuel_burn_per_hour: Optional[float] = None
    atl_record_count: int
    incomplete_record_count: int
    invalid_record_count: int


class PeriodTotals(BaseModel):
    total_flight_hours: float
    total_fuel_gallons: float
    total_oil_quarts: float
    fuel_burn_per_hour: Optional[float] = None
    atl_record_count: int
    incomplete_record_count: int
    invalid_record_count: int


class AircraftPeriodBreakdown(BaseModel):
    period_key: str
    period_label: str
    aircraft: List[AircraftFuelMetrics]
    totals: PeriodTotals


class AircraftFuelReportResponse(BaseModel):
    period: FuelReportPeriod
    filters: AircraftFuelReportFilters
    categories: List[str]
    series: List[ChartSeries]
    aircraft_breakdown: List[AircraftPeriodBreakdown]
    grand_total: PeriodTotals


class AircraftFuelReportQuery(BaseModel):
    """Validated query parameters for the fuel report endpoint."""

    period: FuelReportPeriod
    year: int = Field(..., ge=1900, le=2100)
    month: Optional[int] = Field(None, ge=1, le=12)
    week: Optional[int] = Field(None, ge=1, le=53)
    aircraft_id: Optional[int] = Field(None, ge=1)

    @root_validator
    def _require_period_fields(cls, values):
        period = values.get("period")
        month = values.get("month")
        week = values.get("week")

        if period == FuelReportPeriod.monthly:
            if month is None:
                raise ValueError("month is required when period=monthly")
        elif period == FuelReportPeriod.weekly:
            if week is None:
                raise ValueError("week is required when period=weekly")
        elif period == FuelReportPeriod.yearly:
            # month/week are ignored for yearly; leave as provided (typically null)
            pass

        return values

    @validator("period", pre=True)
    def _normalize_period(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v
