"""Unit tests for monthly aircraft fuel report formulas and aggregation."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.aircraft_fuel_report_service import (
    build_fuel_report,
    fuel_burn_per_hour,
    fuel_consumed,
    invalidate_fuel_report_cache,
    month_label,
    oil_consumed,
    process_atl_rows,
)


def _row(**kwargs):
    defaults = dict(
        id=1,
        sequence_no="1001",
        aircraft_fk=10,
        registration="rp-c12",
        origin_date=date(2026, 1, 15),
        airframe_run_time=Decimal("2.5"),
        fuel_qty_left_uplift_qty=Decimal("0"),
        fuel_qty_right_uplift_qty=Decimal("0"),
        fuel_qty_left_prior_departure=Decimal("18"),
        fuel_qty_right_prior_departure=Decimal("17"),
        fuel_qty_left_after_on_blks=Decimal("13"),
        fuel_qty_right_after_on_blks=Decimal("10"),
        oil_qty_uplift_qty=Decimal("0"),
        oil_qty_prior_departure=Decimal("8"),
        oil_qty_after_on_blks=Decimal("6"),
        number_of_landings=2,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_fuel_consumed_workbook_formula():
    """(18+17) − (13+10) = 12."""
    assert fuel_consumed(
        Decimal("18"), Decimal("17"), Decimal("13"), Decimal("10")
    ) == Decimal("12")


def test_fuel_consumed_nulls_treated_as_zero():
    """Null sides become 0: (18+0) − (13+10) = −5."""
    assert fuel_consumed(
        Decimal("18"), None, Decimal("13"), Decimal("10")
    ) == Decimal("-5")


def test_oil_consumed():
    assert oil_consumed(Decimal("8"), Decimal("6")) == Decimal("2")
    assert oil_consumed(None, Decimal("6")) == Decimal("-6")
    assert oil_consumed(Decimal("8"), None) == Decimal("8")


def test_fuel_burn_null_when_zero_hours_never_nan():
    assert fuel_burn_per_hour(Decimal("12"), Decimal("0")) is None
    assert fuel_burn_per_hour(Decimal("0"), Decimal("0")) is None


def test_fuel_burn_sum_over_sum():
    assert fuel_burn_per_hour(Decimal("30"), Decimal("3")) == 10.0
    assert fuel_burn_per_hour(Decimal("10"), Decimal("3")) == 3.33


def test_month_label():
    assert month_label(2026, 1) == "Jan-26"
    assert month_label(2026, 6) == "Jun-26"


def test_zero_run_time_yields_null_burn_in_report():
    rows = [
        _row(
            airframe_run_time=Decimal("0"),
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("5"),
            fuel_qty_right_after_on_blks=Decimal("5"),
        )
    ]
    report = build_fuel_report(rows, start_month="2026-01", end_month="2026-01")
    assert report.monthly[0].hours == 0.0
    assert report.monthly[0].fuel_gal == 10.0
    assert report.monthly[0].fuel_burn_per_hour is None
    assert report.summary.avg_fuel_burn_per_hour is None


def test_run_time_falls_back_to_tachometer_total():
    rows = [
        _row(
            airframe_run_time=None,
            auto_airframe_run_time=None,
            tachometer_total=Decimal("1.75"),
        )
    ]
    state = process_atl_rows(rows)
    assert state.grand.hours == Decimal("1.75")


def test_month_date_fallback_when_origin_missing():
    rows = [
        _row(
            origin_date=None,
            month_date=date(2026, 3, 12),
            airframe_run_time=Decimal("1"),
        )
    ]
    report = build_fuel_report(rows, start_month="2026-03", end_month="2026-03")
    assert report.monthly[0].month == "2026-03"
    assert report.monthly[0].hours == 1.0


def test_null_fuel_fields_treated_as_zero():
    """Null PRIOR/AFTER sides become 0 — fuel still aggregated, no missing flag."""
    rows = [
        _row(
            airframe_run_time=Decimal("1.5"),
            fuel_qty_left_prior_departure=None,
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("5"),
            fuel_qty_right_after_on_blks=Decimal("5"),
        )
    ]
    state = process_atl_rows(rows)
    assert state.grand.hours == Decimal("1.5")
    # (0+10) − (5+5) = 0
    assert state.grand.fuel == Decimal("0")
    assert not any(f.code == "missing_fuel_fields" for f in state.flags)


def test_negative_fuel_flagged_not_dropped():
    rows = [
        _row(
            fuel_qty_left_prior_departure=Decimal("5"),
            fuel_qty_right_prior_departure=Decimal("5"),
            fuel_qty_left_after_on_blks=Decimal("8"),
            fuel_qty_right_after_on_blks=Decimal("5"),
        )
    ]
    state = process_atl_rows(rows)
    assert state.grand.fuel == Decimal("-3")
    assert any(f.code == "negative_fuel_consumed" for f in state.flags)


def test_fuel_chain_break_flagged():
    rows = [
        _row(
            id=1,
            sequence_no="1",
            origin_date=date(2026, 1, 1),
            fuel_qty_left_prior_departure=Decimal("20"),
            fuel_qty_right_prior_departure=Decimal("20"),
            fuel_qty_left_after_on_blks=Decimal("10"),
            fuel_qty_right_after_on_blks=Decimal("10"),
            fuel_qty_left_uplift_qty=Decimal("0"),
            fuel_qty_right_uplift_qty=Decimal("0"),
        ),
        _row(
            id=2,
            sequence_no="2",
            origin_date=date(2026, 1, 2),
            # PRIOR should be ~20 (prev AFTER+uplift) but is 50
            fuel_qty_left_prior_departure=Decimal("25"),
            fuel_qty_right_prior_departure=Decimal("25"),
            fuel_qty_left_after_on_blks=Decimal("15"),
            fuel_qty_right_after_on_blks=Decimal("15"),
        ),
    ]
    state = process_atl_rows(rows)
    assert any(f.code == "fuel_chain_break" for f in state.flags)


def test_build_report_empty_months_included_in_range():
    report = build_fuel_report([], start_month="2026-01", end_month="2026-03")
    assert report.monthly == []
    assert report.summary.total_hours == 0.0


def test_build_report_fills_gap_months_when_data_exists():
    rows = [
        _row(origin_date=date(2026, 1, 10)),
        _row(id=2, sequence_no="2", origin_date=date(2026, 3, 10)),
    ]
    report = build_fuel_report(rows, start_month="2026-01", end_month="2026-03")
    assert [m.month for m in report.monthly] == ["2026-01", "2026-02", "2026-03"]
    assert report.monthly[1].hours == 0.0


def test_build_report_aggregates_by_month_and_aircraft():
    rows = [
        _row(
            origin_date=date(2026, 1, 10),
            registration="RP-C12",
            airframe_run_time=Decimal("2"),
            number_of_landings=1,
        ),
        _row(
            id=2,
            sequence_no="1002",
            origin_date=date(2026, 1, 20),
            registration="RP-C14",
            airframe_run_time=Decimal("3"),
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("5"),
            fuel_qty_right_after_on_blks=Decimal("5"),
            oil_qty_prior_departure=Decimal("4"),
            oil_qty_after_on_blks=Decimal("3"),
            number_of_landings=2,
        ),
        _row(
            id=3,
            sequence_no="1003",
            origin_date=date(2026, 2, 5),
            registration="RP-C12",
            airframe_run_time=Decimal("1"),
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("8"),
            fuel_qty_right_after_on_blks=Decimal("7"),
            oil_qty_prior_departure=Decimal("2"),
            oil_qty_after_on_blks=Decimal("1"),
            number_of_landings=1,
        ),
    ]
    report = build_fuel_report(rows, start_month="2026-01", end_month="2026-02")
    jan = report.monthly[0]
    assert jan.month == "2026-01"
    assert jan.month_label == "Jan-26"
    assert jan.hours == 5.0
    assert jan.fuel_gal == 22.0  # 12 + 10
    assert jan.landings == 3
    assert jan.fuel_burn_per_hour == 4.4  # 22 / 5 rounded to 2 dp
    tails = {a.tail_number for a in jan.aircraft_breakdown}
    assert tails == {"RP-C12", "RP-C14"}

    assert report.summary.total_hours == 6.0
    assert report.summary.total_fuel_gal == 27.0  # 22 + 5
    assert report.summary.total_landings == 4
    assert report.meta.source == "ATL Logbook"


def test_cache_invalidate_clears():
    invalidate_fuel_report_cache()
    rows = [_row()]
    report = build_fuel_report(rows, start_month="2026-01", end_month="2026-01")
    assert report.monthly[0].hours == 2.5
