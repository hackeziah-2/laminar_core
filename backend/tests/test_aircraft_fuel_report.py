"""Unit tests for aircraft fuel report formulas and period buckets."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.aircraft_fuel_report_schema import FuelReportPeriod
from app.services.aircraft_fuel_report_service import (
    build_fuel_report,
    categories_for_period,
    category_index_for_date,
    classify_atl_row,
    fuel_burn_rate,
    month_calendar_week,
    normalize_registration,
    resolve_period_bounds,
    round2,
)


def _row(**kwargs):
    defaults = dict(
        id=1,
        aircraft_fk=10,
        registration="rp-c12",
        atl_date_time_reported=datetime(2026, 8, 5, 10, 0, 0),
        airframe_flight_time=Decimal("2.5"),
        fuel_qty_left_prior_departure=Decimal("18"),
        fuel_qty_right_prior_departure=Decimal("17"),
        fuel_qty_left_after_on_blks=Decimal("13"),
        fuel_qty_right_after_on_blks=Decimal("10"),
        oil_qty_prior_departure=Decimal("8"),
        oil_qty_after_on_blks=Decimal("6"),
        work_status="APPROVED",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_fuel_used_formula_example():
    """Left 18-13=5, right 17-10=7, total 12."""
    status, hours, left, right, oil = classify_atl_row(_row())
    assert status == "complete"
    assert hours == Decimal("2.5")
    assert left == Decimal("5")
    assert right == Decimal("7")
    assert oil == Decimal("2")


def test_missing_values_are_incomplete_not_zero():
    status, hours, left, right, oil = classify_atl_row(
        _row(fuel_qty_left_after_on_blks=None)
    )
    assert status == "incomplete"
    assert hours is None
    assert left is None


def test_negative_fuel_is_invalid():
    status, *_ = classify_atl_row(
        _row(
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("12"),
        )
    )
    assert status == "invalid"


def test_fuel_burn_is_sum_over_sum_not_average_of_rates():
    """
    Two ATLs: (12 gal / 2 h) and (6 gal / 1 h).
    Average of rates = 6; correct burn = 18/3 = 6.0 still same,
    so use unequal rates: (10/2=5) and (20/1=20) → avg would be 12.5; SUM=30/3=10.
    """
    total_fuel = Decimal("30")
    total_hours = Decimal("3")
    assert fuel_burn_rate(total_fuel, total_hours) == Decimal("10")
    assert round2(fuel_burn_rate(Decimal("30"), Decimal("0"))) is None


def test_fuel_burn_null_when_zero_hours():
    assert fuel_burn_rate(Decimal("12"), Decimal("0")) is None


def test_normalize_registration():
    assert normalize_registration("  rp-c12 ") == "RP-C12"


def test_month_calendar_week_buckets():
    assert month_calendar_week(1) == 1
    assert month_calendar_week(7) == 1
    assert month_calendar_week(8) == 2
    assert month_calendar_week(14) == 2
    assert month_calendar_week(15) == 3
    assert month_calendar_week(22) == 4
    assert month_calendar_week(28) == 4
    assert month_calendar_week(29) == 5
    assert month_calendar_week(31) == 5


def test_categories_lengths():
    assert len(categories_for_period(FuelReportPeriod.weekly)) == 7
    assert len(categories_for_period(FuelReportPeriod.monthly)) == 5
    assert len(categories_for_period(FuelReportPeriod.yearly)) == 12


def test_category_index_weekly_monday_sunday():
    # 2026-08-03 is Monday of ISO week 32
    assert category_index_for_date(FuelReportPeriod.weekly, date(2026, 8, 3)) == 0
    assert category_index_for_date(FuelReportPeriod.weekly, date(2026, 8, 9)) == 6


def test_resolve_period_bounds_weekly_iso():
    start, end = resolve_period_bounds(FuelReportPeriod.weekly, 2026, None, 32)
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 9)


def test_resolve_period_bounds_monthly():
    start, end = resolve_period_bounds(FuelReportPeriod.monthly, 2026, 8, None)
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_resolve_period_bounds_yearly():
    start, end = resolve_period_bounds(FuelReportPeriod.yearly, 2026, None, None)
    assert start == date(2026, 1, 1)
    assert end == date(2026, 12, 31)


def test_build_report_empty_categories_included():
    report = build_fuel_report(
        [],
        period=FuelReportPeriod.yearly,
        year=2026,
        month=None,
        week=None,
        aircraft_id=None,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert report.categories == [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    assert len(report.aircraft_breakdown) == 12
    for series in report.series:
        assert len(series.data) == 12
    assert report.grand_total.atl_record_count == 0
    assert report.series[2].data == [None] * 12  # burn null with zero hours


def test_build_report_aggregates_and_counts():
    rows = [
        _row(
            id=1,
            atl_date_time_reported=datetime(2026, 1, 10, 8, 0),
            airframe_flight_time=Decimal("2"),
            fuel_qty_left_prior_departure=Decimal("18"),
            fuel_qty_left_after_on_blks=Decimal("13"),
            fuel_qty_right_prior_departure=Decimal("17"),
            fuel_qty_right_after_on_blks=Decimal("10"),
            oil_qty_prior_departure=Decimal("8"),
            oil_qty_after_on_blks=Decimal("6"),
        ),
        # incomplete
        _row(
            id=2,
            atl_date_time_reported=datetime(2026, 1, 11, 8, 0),
            airframe_flight_time=None,
        ),
        # invalid (negative left)
        _row(
            id=3,
            atl_date_time_reported=datetime(2026, 1, 12, 8, 0),
            fuel_qty_left_prior_departure=Decimal("5"),
            fuel_qty_left_after_on_blks=Decimal("10"),
        ),
        # February complete
        _row(
            id=4,
            atl_date_time_reported=datetime(2026, 2, 5, 8, 0),
            airframe_flight_time=Decimal("1"),
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("8"),
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_right_after_on_blks=Decimal("7"),
            oil_qty_prior_departure=Decimal("4"),
            oil_qty_after_on_blks=Decimal("3"),
        ),
    ]
    report = build_fuel_report(
        rows,
        period=FuelReportPeriod.yearly,
        year=2026,
        month=None,
        week=None,
        aircraft_id=None,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )

    # Jan: 12 gal / 2 h = 6.0; Feb: 5 gal / 1 h = 5.0
    assert report.series[0].data[0] == 2.0
    assert report.series[1].data[0] == 12.0
    assert report.series[2].data[0] == 6.0
    assert report.series[0].data[1] == 1.0
    assert report.series[1].data[1] == 5.0
    assert report.series[2].data[1] == 5.0

    jan = report.aircraft_breakdown[0]
    assert jan.period_key == "2026-01"
    assert jan.totals.incomplete_record_count == 1
    assert jan.totals.invalid_record_count == 1
    assert jan.totals.atl_record_count == 3
    assert jan.aircraft[0].aircraft_registration == "RP-C12"
    assert jan.aircraft[0].left_fuel_gallons == 5.0
    assert jan.aircraft[0].right_fuel_gallons == 7.0

    # Grand: 12+5=17 fuel, 2+1=3 hours → burn 17/3 ≈ 5.67
    assert report.grand_total.total_fuel_gallons == 17.0
    assert report.grand_total.total_flight_hours == 3.0
    assert report.grand_total.fuel_burn_per_hour == 5.67
    assert report.grand_total.incomplete_record_count == 1
    assert report.grand_total.invalid_record_count == 1
    assert report.grand_total.atl_record_count == 4


def test_build_report_monthly_week_buckets():
    rows = [
        _row(atl_date_time_reported=datetime(2026, 8, 3, 9, 0)),   # Week 1
        _row(id=2, atl_date_time_reported=datetime(2026, 8, 20, 9, 0)),  # Week 3
        _row(id=3, atl_date_time_reported=datetime(2026, 8, 30, 9, 0)),  # Week 5
    ]
    report = build_fuel_report(
        rows,
        period=FuelReportPeriod.monthly,
        year=2026,
        month=8,
        week=None,
        aircraft_id=None,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    assert report.categories == ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"]
    assert report.series[0].data[0] == 2.5
    assert report.series[0].data[1] == 0.0
    assert report.series[0].data[2] == 2.5
    assert report.series[0].data[4] == 2.5
    assert report.aircraft_breakdown[0].period_key == "2026-08-W1"
    assert report.aircraft_breakdown[4].period_label == "Week 5"


def test_build_report_weekly_weekday_buckets():
    # ISO week 32 of 2026: Mon 2026-08-03 … Sun 2026-08-09
    rows = [
        _row(atl_date_time_reported=datetime(2026, 8, 3, 9, 0)),  # Mon
        _row(id=2, atl_date_time_reported=datetime(2026, 8, 9, 9, 0)),  # Sun
    ]
    report = build_fuel_report(
        rows,
        period=FuelReportPeriod.weekly,
        year=2026,
        month=None,
        week=32,
        aircraft_id=None,
        start_date=date(2026, 8, 3),
        end_date=date(2026, 8, 9),
    )
    assert report.categories[0] == "Mon"
    assert report.categories[6] == "Sun"
    assert report.series[0].data[0] == 2.5
    assert report.series[0].data[6] == 2.5
    assert report.aircraft_breakdown[0].period_key == "2026-08-03"
    assert report.aircraft_breakdown[6].period_key == "2026-08-09"
