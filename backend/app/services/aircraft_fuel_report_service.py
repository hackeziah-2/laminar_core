"""Aircraft Fuel Consumption Dashboard — period buckets and aggregations."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.aircraft_fuel_report import fetch_fuel_report_atl_rows
from app.schemas.aircraft_fuel_report_schema import (
    AircraftFuelMetrics,
    AircraftFuelReportFilters,
    AircraftFuelReportQuery,
    AircraftFuelReportResponse,
    AircraftPeriodBreakdown,
    ChartSeries,
    FuelReportPeriod,
    PeriodTotals,
)

_TWO_PLACES = Decimal("0.01")
_ZERO = Decimal("0")

WEEKDAY_LABELS: Tuple[str, ...] = (
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
)
MONTH_LABELS: Tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
MONTHLY_WEEK_LABELS: Tuple[str, ...] = (
    "Week 1",
    "Week 2",
    "Week 3",
    "Week 4",
    "Week 5",
)


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def round2(value: Optional[Decimal]) -> Optional[float]:
    """Round Decimal to two places; return None when input is None."""
    if value is None:
        return None
    quantized = value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return float(quantized)


def fuel_burn_rate(
    total_fuel: Decimal,
    total_hours: Decimal,
) -> Optional[Decimal]:
    """SUM(fuel) / SUM(hours); None when hours are zero."""
    if total_hours == _ZERO:
        return None
    return total_fuel / total_hours


def resolve_period_bounds(
    period: FuelReportPeriod,
    year: int,
    month: Optional[int],
    week: Optional[int],
) -> Tuple[date, date]:
    """Return inclusive start/end dates for the reporting window (Asia/Manila calendar)."""
    if period == FuelReportPeriod.yearly:
        return date(year, 1, 1), date(year, 12, 31)

    if period == FuelReportPeriod.monthly:
        assert month is not None
        last_day = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    # weekly — ISO week (Monday–Sunday)
    assert week is not None
    try:
        start = date.fromisocalendar(year, week, 1)
        end = date.fromisocalendar(year, week, 7)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid ISO week {week} for year {year}",
        ) from exc
    return start, end


def categories_for_period(period: FuelReportPeriod) -> List[str]:
    if period == FuelReportPeriod.weekly:
        return list(WEEKDAY_LABELS)
    if period == FuelReportPeriod.monthly:
        return list(MONTHLY_WEEK_LABELS)
    return list(MONTH_LABELS)


def month_calendar_week(day: int) -> int:
    """Map day-of-month to Week 1–5 (days 1–7, 8–14, 15–21, 22–28, 29–31)."""
    if day <= 7:
        return 1
    if day <= 14:
        return 2
    if day <= 21:
        return 3
    if day <= 28:
        return 4
    return 5


def category_index_for_date(
    period: FuelReportPeriod,
    reported: date,
) -> int:
    """Zero-based index into categories_for_period for a reporting date."""
    if period == FuelReportPeriod.weekly:
        return reported.weekday()  # Monday=0 … Sunday=6
    if period == FuelReportPeriod.monthly:
        return month_calendar_week(reported.day) - 1
    return reported.month - 1


def period_key_and_label(
    period: FuelReportPeriod,
    year: int,
    month: Optional[int],
    week: Optional[int],
    category_index: int,
    *,
    week_start: Optional[date] = None,
) -> Tuple[str, str]:
    if period == FuelReportPeriod.yearly:
        m = category_index + 1
        return f"{year}-{m:02d}", MONTH_LABELS[category_index]

    if period == FuelReportPeriod.monthly:
        assert month is not None
        w = category_index + 1
        return f"{year}-{month:02d}-W{w}", MONTHLY_WEEK_LABELS[category_index]

    assert week_start is not None
    day = week_start + timedelta(days=category_index)
    return day.isoformat(), WEEKDAY_LABELS[category_index]


@dataclass
class _Accumulator:
    flight_hours: Decimal = _ZERO
    left_fuel: Decimal = _ZERO
    right_fuel: Decimal = _ZERO
    total_fuel: Decimal = _ZERO
    oil: Decimal = _ZERO
    atl_record_count: int = 0
    incomplete_record_count: int = 0
    invalid_record_count: int = 0

    def add_complete(
        self,
        *,
        hours: Decimal,
        left: Decimal,
        right: Decimal,
        oil: Decimal,
    ) -> None:
        self.flight_hours += hours
        self.left_fuel += left
        self.right_fuel += right
        self.total_fuel += left + right
        self.oil += oil
        self.atl_record_count += 1

    def mark_incomplete(self) -> None:
        self.incomplete_record_count += 1
        self.atl_record_count += 1

    def mark_invalid(self) -> None:
        self.invalid_record_count += 1
        self.atl_record_count += 1

    def merge(self, other: "_Accumulator") -> None:
        self.flight_hours += other.flight_hours
        self.left_fuel += other.left_fuel
        self.right_fuel += other.right_fuel
        self.total_fuel += other.total_fuel
        self.oil += other.oil
        self.atl_record_count += other.atl_record_count
        self.incomplete_record_count += other.incomplete_record_count
        self.invalid_record_count += other.invalid_record_count


def classify_atl_row(
    row: Any,
) -> Tuple[str, Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Classify one ATL row.

    Returns (status, hours, left_fuel_used, right_fuel_used, oil_used)
    where status is 'complete' | 'incomplete' | 'invalid'.
    """
    hours = _to_decimal(row.airframe_flight_time)
    left_prior = _to_decimal(row.fuel_qty_left_prior_departure)
    right_prior = _to_decimal(row.fuel_qty_right_prior_departure)
    left_after = _to_decimal(row.fuel_qty_left_after_on_blks)
    right_after = _to_decimal(row.fuel_qty_right_after_on_blks)
    oil_prior = _to_decimal(row.oil_qty_prior_departure)
    oil_after = _to_decimal(row.oil_qty_after_on_blks)

    if None in (
        hours,
        left_prior,
        right_prior,
        left_after,
        right_after,
        oil_prior,
        oil_after,
    ):
        return "incomplete", None, None, None, None

    left_used = left_prior - left_after
    right_used = right_prior - right_after
    oil_used = oil_prior - oil_after

    if left_used < _ZERO or right_used < _ZERO:
        return "invalid", None, None, None, None

    return "complete", hours, left_used, right_used, oil_used


def normalize_registration(registration: Optional[str]) -> str:
    if registration is None:
        return ""
    return registration.strip().upper()


def _acc_to_period_totals(acc: _Accumulator) -> PeriodTotals:
    burn = fuel_burn_rate(acc.total_fuel, acc.flight_hours)
    return PeriodTotals(
        total_flight_hours=round2(acc.flight_hours) or 0.0,
        total_fuel_gallons=round2(acc.total_fuel) or 0.0,
        total_oil_quarts=round2(acc.oil) or 0.0,
        fuel_burn_per_hour=round2(burn),
        atl_record_count=acc.atl_record_count,
        incomplete_record_count=acc.incomplete_record_count,
        invalid_record_count=acc.invalid_record_count,
    )


def _acc_to_aircraft_metrics(
    aircraft_id: int,
    registration: str,
    acc: _Accumulator,
) -> AircraftFuelMetrics:
    burn = fuel_burn_rate(acc.total_fuel, acc.flight_hours)
    return AircraftFuelMetrics(
        aircraft_id=aircraft_id,
        aircraft_registration=registration,
        total_flight_hours=round2(acc.flight_hours) or 0.0,
        left_fuel_gallons=round2(acc.left_fuel) or 0.0,
        right_fuel_gallons=round2(acc.right_fuel) or 0.0,
        total_fuel_gallons=round2(acc.total_fuel) or 0.0,
        total_oil_quarts=round2(acc.oil) or 0.0,
        fuel_burn_per_hour=round2(burn),
        atl_record_count=acc.atl_record_count,
        incomplete_record_count=acc.incomplete_record_count,
        invalid_record_count=acc.invalid_record_count,
    )


def build_fuel_report(
    rows: Sequence[Any],
    *,
    period: FuelReportPeriod,
    year: int,
    month: Optional[int],
    week: Optional[int],
    aircraft_id: Optional[int],
    start_date: date,
    end_date: date,
) -> AircraftFuelReportResponse:
    """Aggregate ATL rows into chart series, aircraft breakdown, and grand totals."""
    categories = categories_for_period(period)
    n = len(categories)

    # category_index -> registration -> accumulator
    by_cat_aircraft: List[Dict[str, _Accumulator]] = [dict() for _ in range(n)]
    # registration -> (aircraft_id, display registration)
    aircraft_meta: Dict[str, Tuple[int, str]] = {}
    # category-level totals (all aircraft)
    by_cat_totals: List[_Accumulator] = [_Accumulator() for _ in range(n)]
    grand = _Accumulator()

    for row in rows:
        reported_dt: Optional[datetime] = row.atl_date_time_reported
        if reported_dt is None:
            continue
        reported = reported_dt.date() if isinstance(reported_dt, datetime) else reported_dt

        # Extra safety for weekly ISO year boundaries (query window may include adjacent days)
        if period == FuelReportPeriod.weekly:
            iso = reported.isocalendar()
            if iso.year != year or iso.week != week:
                continue
        elif period == FuelReportPeriod.monthly:
            if reported.year != year or reported.month != month:
                continue
        elif period == FuelReportPeriod.yearly:
            if reported.year != year:
                continue

        idx = category_index_for_date(period, reported)
        reg_key = normalize_registration(row.registration)
        aircraft_meta[reg_key] = (int(row.aircraft_fk), reg_key)

        status, hours, left, right, oil = classify_atl_row(row)
        aircraft_acc = by_cat_aircraft[idx].setdefault(reg_key, _Accumulator())

        if status == "incomplete":
            aircraft_acc.mark_incomplete()
            by_cat_totals[idx].mark_incomplete()
            grand.mark_incomplete()
            continue
        if status == "invalid":
            aircraft_acc.mark_invalid()
            by_cat_totals[idx].mark_invalid()
            grand.mark_invalid()
            continue

        assert hours is not None and left is not None and right is not None and oil is not None
        aircraft_acc.add_complete(hours=hours, left=left, right=right, oil=oil)
        by_cat_totals[idx].add_complete(hours=hours, left=left, right=right, oil=oil)
        grand.add_complete(hours=hours, left=left, right=right, oil=oil)

    # Chart series (category totals)
    hours_data: List[Optional[float]] = []
    fuel_data: List[Optional[float]] = []
    burn_data: List[Optional[float]] = []
    for acc in by_cat_totals:
        hours_data.append(round2(acc.flight_hours) or 0.0)
        fuel_data.append(round2(acc.total_fuel) or 0.0)
        burn_data.append(round2(fuel_burn_rate(acc.total_fuel, acc.flight_hours)))

    series = [
        ChartSeries(
            key="flight_hours",
            name="Hours",
            chart_type="bar",
            unit="hours",
            y_axis="left",
            data=hours_data,
        ),
        ChartSeries(
            key="fuel_gallons",
            name="Fuel (Gal)",
            chart_type="bar",
            unit="gallons",
            y_axis="left",
            data=fuel_data,
        ),
        ChartSeries(
            key="fuel_burn_per_hour",
            name="Fuel Burn / Hour",
            chart_type="line",
            unit="gal/hour",
            y_axis="right",
            data=burn_data,
        ),
    ]

    week_start = start_date if period == FuelReportPeriod.weekly else None
    breakdown: List[AircraftPeriodBreakdown] = []
    for idx in range(n):
        period_key, period_label = period_key_and_label(
            period,
            year,
            month,
            week,
            idx,
            week_start=week_start,
        )
        aircraft_list: List[AircraftFuelMetrics] = []
        for reg_key in sorted(by_cat_aircraft[idx].keys()):
            ac_id, reg = aircraft_meta[reg_key]
            aircraft_list.append(
                _acc_to_aircraft_metrics(ac_id, reg, by_cat_aircraft[idx][reg_key])
            )
        breakdown.append(
            AircraftPeriodBreakdown(
                period_key=period_key,
                period_label=period_label,
                aircraft=aircraft_list,
                totals=_acc_to_period_totals(by_cat_totals[idx]),
            )
        )

    return AircraftFuelReportResponse(
        period=period,
        filters=AircraftFuelReportFilters(
            year=year,
            month=month if period == FuelReportPeriod.monthly else None,
            week=week if period == FuelReportPeriod.weekly else None,
            aircraft_id=aircraft_id,
            start_date=start_date,
            end_date=end_date,
        ),
        categories=categories,
        series=series,
        aircraft_breakdown=breakdown,
        grand_total=_acc_to_period_totals(grand),
    )


async def get_aircraft_fuel_report(
    session: AsyncSession,
    query: AircraftFuelReportQuery,
) -> AircraftFuelReportResponse:
    """Fetch ATLs and build the fuel consumption dashboard payload."""
    start_date, end_date = resolve_period_bounds(
        query.period,
        query.year,
        query.month,
        query.week,
    )
    rows = await fetch_fuel_report_atl_rows(
        session,
        start_date=start_date,
        end_date=end_date,
        aircraft_id=query.aircraft_id,
    )
    return build_fuel_report(
        rows,
        period=query.period,
        year=query.year,
        month=query.month,
        week=query.week,
        aircraft_id=query.aircraft_id,
        start_date=start_date,
        end_date=end_date,
    )
