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


def test_null_off_blocks_date_excluded_from_report():
    """Rows without off_blocks_date (origin_date) are skipped."""
    rows = [
        _row(
            origin_date=None,
            month_date=date(2026, 3, 12),
            airframe_run_time=Decimal("1"),
        )
    ]
    report = build_fuel_report(rows, start_month="2026-03", end_month="2026-03")
    assert report.monthly == []
    assert report.summary.total_hours == 0.0


def test_ym_to_exclusive_range_half_open():
    from app.services.aircraft_fuel_report_service import (
        exclusive_month_end,
        ym_to_exclusive_range,
    )

    start, end_excl = ym_to_exclusive_range("2023-01", "2026-12")
    assert start == date(2023, 1, 1)
    assert end_excl == date(2027, 1, 1)
    assert exclusive_month_end(2026, 12) == date(2027, 1, 1)
    assert exclusive_month_end(2026, 7) == date(2026, 8, 1)


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
    assert report.meta.fuel_unit == "gallons"


def test_yoy_years_derived_from_start_end_month_range():
    """When years is omitted, YoY columns follow start_month..end_month years."""
    rows = [
        _row(
            origin_date=date(2023, 1, 10),
            airframe_run_time=Decimal("10"),
        ),
        _row(
            id=2,
            sequence_no="2",
            origin_date=date(2023, 6, 10),
            airframe_run_time=Decimal("20"),
        ),
        _row(
            id=3,
            sequence_no="3",
            origin_date=date(2024, 3, 10),
            airframe_run_time=Decimal("30"),
        ),
    ]
    single = build_fuel_report(
        rows,
        start_month="2023-01",
        end_month="2023-12",
    )
    assert single.yoy_flying_hours.years == [2023]
    assert single.yoy_flying_hours.months[0].values == {"2023": 10.0}
    assert single.yoy_flying_hours.months[5].values == {"2023": 20.0}
    assert single.yoy_flying_hours.grand_total == {"2023": 30.0}

    multi = build_fuel_report(
        rows,
        start_month="2023-01",
        end_month="2024-12",
    )
    assert multi.yoy_flying_hours.years == [2023, 2024]
    assert multi.yoy_flying_hours.months[2].values == {"2023": 0.0, "2024": 30.0}


def test_yoy_flying_hours_grand_total_skips_empty_months():
    """grand_total / average only cover months with hours > 0 for that year."""
    rows = [
        _row(
            origin_date=date(2025, 1, 10),
            airframe_run_time=Decimal("100"),
        ),
        _row(
            id=2,
            sequence_no="2",
            origin_date=date(2025, 2, 10),
            airframe_run_time=Decimal("200"),
        ),
        _row(
            id=3,
            sequence_no="3",
            origin_date=date(2026, 1, 10),
            airframe_run_time=Decimal("150"),
        ),
        # July YoY jump: 50 → 250 = 5x → large_yoy_variance
        _row(
            id=4,
            sequence_no="4",
            origin_date=date(2025, 7, 10),
            airframe_run_time=Decimal("50"),
        ),
        _row(
            id=5,
            sequence_no="5",
            origin_date=date(2026, 7, 10),
            airframe_run_time=Decimal("250"),
        ),
    ]
    report = build_fuel_report(
        rows,
        start_month="2026-01",
        end_month="2026-01",
        years=[2025, 2026],
    )
    yoy = report.yoy_flying_hours
    assert yoy.years == [2025, 2026]
    assert len(yoy.months) == 12
    assert yoy.months[0].month == "January"
    assert yoy.months[0].values == {"2025": 100.0, "2026": 150.0}
    assert yoy.months[6].month == "July"
    assert yoy.months[6].values == {"2025": 50.0, "2026": 250.0}
    assert yoy.months[6].flag == "large_yoy_variance"
    # 2025: Jan+Feb+Jul = 350 over 3 months; 2026: Jan+Jul = 400 over 2 months
    assert yoy.grand_total == {"2025": 350.0, "2026": 400.0}
    assert yoy.average_fh == {"2025": 350.0 / 3, "2026": 200.0}
    assert any(f.code == "large_yoy_variance" for f in report.data_quality_flags)
    # Monthly series still scoped to start/end only
    assert [m.month for m in report.monthly] == ["2026-01"]
    assert report.summary.total_hours == 150.0


def test_yoy_empty_years_zeroed_not_404():
    report = build_fuel_report(
        [],
        start_month="2099-01",
        end_month="2099-01",
        years=[2098, 2099],
    )
    assert report.yoy_flying_hours.years == [2098, 2099]
    assert len(report.yoy_flying_hours.months) == 12
    assert report.yoy_flying_hours.grand_total == {"2098": 0.0, "2099": 0.0}
    assert report.yoy_flying_hours.average_fh == {"2098": 0.0, "2099": 0.0}
    assert all(
        m.values == {"2098": 0.0, "2099": 0.0} for m in report.yoy_flying_hours.months
    )


def test_aircraft_month_breakdown_shared_burn_and_zero_hours_null():
    rows = [
        _row(
            registration="RP-C12",
            origin_date=date(2025, 4, 5),
            airframe_run_time=Decimal("10"),
            fuel_qty_left_prior_departure=Decimal("100"),
            fuel_qty_right_prior_departure=Decimal("100"),
            fuel_qty_left_after_on_blks=Decimal("0"),
            fuel_qty_right_after_on_blks=Decimal("0"),
        ),
        _row(
            id=2,
            sequence_no="2",
            registration="RP-C14",
            origin_date=date(2025, 4, 5),
            airframe_run_time=Decimal("10"),
            fuel_qty_left_prior_departure=Decimal("100"),
            fuel_qty_right_prior_departure=Decimal("100"),
            fuel_qty_left_after_on_blks=Decimal("0"),
            fuel_qty_right_after_on_blks=Decimal("0"),
        ),
        _row(
            id=3,
            sequence_no="3",
            registration="RP-C20",
            origin_date=date(2025, 4, 6),
            airframe_run_time=Decimal("10"),
            # fuel=50 → burn=5 vs peer median 20 → 4x outlier
            fuel_qty_left_prior_departure=Decimal("30"),
            fuel_qty_right_prior_departure=Decimal("20"),
            fuel_qty_left_after_on_blks=Decimal("0"),
            fuel_qty_right_after_on_blks=Decimal("0"),
        ),
        _row(
            id=4,
            sequence_no="4",
            registration="RP-C99",
            origin_date=date(2025, 4, 7),
            airframe_run_time=Decimal("0"),
            fuel_qty_left_prior_departure=Decimal("10"),
            fuel_qty_right_prior_departure=Decimal("10"),
            fuel_qty_left_after_on_blks=Decimal("5"),
            fuel_qty_right_after_on_blks=Decimal("5"),
        ),
    ]
    report = build_fuel_report(
        rows,
        start_month="2025-04",
        end_month="2025-04",
        years=[2025],
        month_year="2025-04",
    )
    bd = report.aircraft_month_breakdown
    assert bd.month_year == "Apr-25"
    by_tail = {a.tail_number: a for a in bd.aircraft}
    assert by_tail["RP-C12"].hours == 10.0
    assert by_tail["RP-C12"].fuel == 200.0
    assert by_tail["RP-C12"].fuel_burn_per_hour == 20.0
    assert by_tail["RP-C20"].fuel_burn_per_hour == 5.0
    assert by_tail["RP-C20"].flag == "fuel_burn_outlier"
    assert by_tail["RP-C12"].flag is None
    assert by_tail["RP-C99"].hours == 0.0
    assert by_tail["RP-C99"].fuel_burn_per_hour is None
    assert any(f.code == "fuel_burn_outlier" for f in report.data_quality_flags)


def test_aircraft_month_breakdown_empty_when_month_omitted():
    report = build_fuel_report(
        [_row()],
        start_month="2026-01",
        end_month="2026-01",
        years=[2026],
    )
    assert report.aircraft_month_breakdown.month_year is None
    assert report.aircraft_month_breakdown.aircraft == []


def test_cache_invalidate_clears():
    invalidate_fuel_report_cache()
    rows = [_row()]
    report = build_fuel_report(rows, start_month="2026-01", end_month="2026-01")
    assert report.monthly[0].hours == 2.5
