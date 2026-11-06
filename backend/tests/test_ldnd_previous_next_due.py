"""Last Done Tach Due comes from the latest matching Next Due Tach Hours."""

from datetime import date
from types import SimpleNamespace

from app.repository.ldnd_monitoring import select_latest_next_due_tach_hours


def _row(row_id, inspection_type, performed_date_end, next_due):
    return SimpleNamespace(
        id=row_id,
        inspection_type=inspection_type,
        performed_date_end=performed_date_end,
        next_due_tach_hours=next_due,
    )


def test_latest_performed_date_end_supplies_next_due():
    rows = [
        _row(1, "100-Hour Inspection", date(2024, 1, 1), 900),
        _row(2, "100-Hour Inspection", date(2025, 6, 1), 1500.5),
        _row(3, "Annual Inspection", date(2026, 1, 1), 3000),
    ]
    assert (
        select_latest_next_due_tach_hours(rows, "100-hour inspection") == 1500.5
    )


def test_missing_performed_date_does_not_outrank_a_dated_row():
    rows = [
        _row(9, "100-Hour Inspection", None, 4000),
        _row(2, "100-Hour Inspection", date(2025, 6, 1), 1500),
    ]
    assert select_latest_next_due_tach_hours(rows, "100-Hour Inspection") == 1500


def test_same_date_uses_the_greater_id():
    rows = [
        _row(4, "100-Hour Inspection", date(2025, 6, 1), 1100),
        _row(8, "100-Hour Inspection", date(2025, 6, 1), 1800),
    ]
    assert select_latest_next_due_tach_hours(rows, "100-Hour Inspection") == 1800


def test_undated_rows_use_the_greater_id():
    rows = [
        _row(4, "Annual Inspection", None, 100),
        _row(7, "Annual Inspection", None, 250),
    ]
    assert select_latest_next_due_tach_hours(rows, "Annual Inspection") == 250


def test_latest_row_without_next_due_stays_blank():
    rows = [
        _row(1, "100-Hour Inspection", date(2024, 1, 1), 900),
        _row(2, "100-Hour Inspection", date(2025, 6, 1), None),
    ]
    assert select_latest_next_due_tach_hours(rows, "100-Hour Inspection") is None


def test_no_matching_item_stays_blank():
    rows = [_row(1, "Annual Inspection", date(2025, 1, 1), 500)]
    assert select_latest_next_due_tach_hours(rows, "100-Hour Inspection") is None
    assert select_latest_next_due_tach_hours(rows, "   ") is None


def test_editing_excludes_the_current_record():
    rows = [
        _row(5, "100-Hour Inspection", date(2026, 1, 1), 2200),
        _row(3, "100-Hour Inspection", date(2025, 1, 1), 1600),
    ]
    assert (
        select_latest_next_due_tach_hours(
            rows, "100-Hour Inspection", exclude_id=5
        )
        == 1600
    )
    assert (
        select_latest_next_due_tach_hours(
            rows, "100-Hour Inspection", exclude_id=5
        )
        != 2200
    )


def test_invalid_next_due_stays_blank():
    rows = [_row(1, "100-Hour Inspection", date(2025, 1, 1), float("nan"))]
    assert select_latest_next_due_tach_hours(rows, "100-Hour Inspection") is None
