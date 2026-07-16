"""Unit tests for ATL flexible Date Time Reported / Date Time Released import."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pytest

from app.schemas.aircraft_technical_log_schema import (
    AircraftTechnicalLogImportSchema,
    parse_import_reported_released_datetime,
)
from app.services.atl_import_date_time_reported import (
    as_naive_ph,
    combine_date_and_time,
    resolve_date_time_reported,
    try_parse_atl_date_time_reported,
)
from app.services.atl_import_references import AtlImportReferences
from app.services.atl_import_validation import (
    validate_atl_row_schema,
    validate_date_time_reported_mapping,
)
from app.services.excel_import.parsers import (
    INVALID_FLEXIBLE_DATETIME_MESSAGE,
    parse_flexible_datetime,
)


# ---------- parse_flexible_datetime ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("6-May-24 0930Z", datetime(2024, 5, 6, 9, 30, tzinfo=timezone.utc)),
        ("06-May-24 0930Z", datetime(2024, 5, 6, 9, 30, tzinfo=timezone.utc)),
        ("7-MAY-24 0900Z", datetime(2024, 5, 7, 9, 0, tzinfo=timezone.utc)),
        ("01-Mar-24 0738Z", datetime(2024, 3, 1, 7, 38, tzinfo=timezone.utc)),
        ("10-Sept-2024", datetime(2024, 9, 10, 0, 0)),
        ("27-Sept-2024", datetime(2024, 9, 27, 0, 0)),
        ("28-Sept-2024", datetime(2024, 9, 28, 0, 0)),
        ("27-Sep-2024", datetime(2024, 9, 27, 0, 0)),
        ("10-Sep-2024", datetime(2024, 9, 10, 0, 0)),
        ("2024-05-06T09:30:00Z", datetime(2024, 5, 6, 9, 30, tzinfo=timezone.utc)),
        ("2024-05-06 09:30:00", datetime(2024, 5, 6, 9, 30)),
        ("  10-Sept-2024  ", datetime(2024, 9, 10, 0, 0)),
    ],
)
def test_parse_flexible_datetime_supported_formats(raw, expected):
    assert parse_flexible_datetime(raw) == expected


def test_parse_flexible_datetime_empty_null():
    assert parse_flexible_datetime(None) is None
    assert parse_flexible_datetime("") is None
    assert parse_flexible_datetime("  ") is None
    assert parse_flexible_datetime("NULL") is None
    assert parse_flexible_datetime("NaN") is None


def test_parse_flexible_datetime_native_excel_values():
    assert parse_flexible_datetime(datetime(2024, 5, 6, 9, 30)) == datetime(
        2024, 5, 6, 9, 30
    )
    assert parse_flexible_datetime(date(2024, 9, 10)) == datetime(2024, 9, 10, 0, 0)


def test_parse_flexible_datetime_invalid_raises():
    with pytest.raises(ValueError, match="Invalid date"):
        parse_flexible_datetime("invalid-value")


# ---------- Date Time Released (storage / schema) ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Zulu → Asia/Manila naive wall-clock
        ("6-May-24 0930Z", datetime(2024, 5, 6, 17, 30)),
        ("7-MAY-24 0900Z", datetime(2024, 5, 7, 17, 0)),
        ("01-Mar-24 0738Z", datetime(2024, 3, 1, 15, 38)),
        ("10-Sept-2024", datetime(2024, 9, 10, 0, 0)),
        ("27-Sept-2024", datetime(2024, 9, 27, 0, 0)),
        ("28-Sept-2024", datetime(2024, 9, 28, 0, 0)),
        ("2024-05-06T09:30:00Z", datetime(2024, 5, 6, 17, 30)),
    ],
)
def test_date_time_released_flexible_formats(raw, expected):
    assert parse_import_reported_released_datetime(raw) == expected


def test_date_time_released_empty_is_null():
    assert parse_import_reported_released_datetime(None) is None
    assert parse_import_reported_released_datetime("") is None
    assert parse_import_reported_released_datetime("NULL") is None


def test_date_time_released_native_excel_datetime():
    native = datetime(2024, 5, 6, 9, 30)
    assert parse_import_reported_released_datetime(native) == native


def test_date_time_released_invalid_row_error_message():
    inject = {"aircraft_fk": 1, "atl_batch_fk": 1}
    bad, bad_errors = validate_atl_row_schema(
        {
            "sequence_no": "001",
            "date_time_released": "invalid-value",
        },
        excel_row=45,
        inject_fields=inject,
    )
    assert bad is None
    assert len(bad_errors) == 1
    assert bad_errors[0]["column"].lower() == "date time released"
    assert bad_errors[0]["value"] == "invalid-value"
    assert bad_errors[0]["error"] == INVALID_FLEXIBLE_DATETIME_MESSAGE
    assert "expected" not in bad_errors[0]


def test_date_time_released_problem_rows_now_valid():
    inject = {"aircraft_fk": 1, "atl_batch_fk": 1}
    cases = [
        (45, "6-May-24 0930Z", datetime(2024, 5, 6, 17, 30)),
        (46, "7-MAY-24 0900Z", datetime(2024, 5, 7, 17, 0)),
        (113, "10-Sept-2024", datetime(2024, 9, 10, 0, 0)),
        (114, "27-Sept-2024", datetime(2024, 9, 27, 0, 0)),
        (115, "28-Sept-2024", datetime(2024, 9, 28, 0, 0)),
    ]
    for excel_row, raw, expected in cases:
        validated, errors = validate_atl_row_schema(
            {"sequence_no": str(excel_row), "date_time_released": raw},
            excel_row=excel_row,
            inject_fields=inject,
        )
        assert errors == [], f"row {excel_row} should be valid"
        assert validated is not None
        assert validated.date_time_released == expected


# ---------- Date Time Reported ----------


def test_try_parse_empty():
    assert try_parse_atl_date_time_reported(None) == (None, "empty")
    assert try_parse_atl_date_time_reported("") == (None, "empty")
    assert try_parse_atl_date_time_reported("  ") == (None, "empty")


def test_try_parse_valid_manila_naive():
    dt, issue = try_parse_atl_date_time_reported("01-Mar-24 0738")
    assert issue is None
    assert dt == datetime(2024, 3, 1, 7, 38)


def test_try_parse_zulu_converts_to_manila():
    # 07:38 UTC → 15:38 Asia/Manila
    dt, issue = try_parse_atl_date_time_reported("01-Mar-24 0738Z")
    assert issue is None
    assert dt == datetime(2024, 3, 1, 15, 38)


@pytest.mark.parametrize(
    "raw",
    [
        "6-May-24 0930Z",
        "7-MAY-24 0900Z",
        "10-Sept-2024",
        "27-Sept-2024",
        "28-Sept-2024",
    ],
)
def test_try_parse_flexible_reported_formats(raw):
    dt, issue = try_parse_atl_date_time_reported(raw)
    assert issue is None
    assert isinstance(dt, datetime)


def test_try_parse_invalid():
    dt, issue = try_parse_atl_date_time_reported("not-a-date")
    assert dt is None
    assert issue == "invalid"


def test_combine_date_and_time():
    assert combine_date_and_time(date(2024, 3, 1), time(7, 38)) == datetime(
        2024, 3, 1, 7, 38
    )
    assert combine_date_and_time(date(2024, 3, 1), None) == datetime(2024, 3, 1, 0, 0)
    assert combine_date_and_time(None, time(7, 38)) is None


def test_as_naive_ph_from_utc():
    utc = datetime(2024, 3, 1, 7, 38, tzinfo=timezone.utc)
    assert as_naive_ph(utc) == datetime(2024, 3, 1, 15, 38)


def test_scenario_1_empty_origin_uses_imported():
    existing = SimpleNamespace(origin_date=None, origin_time=None)
    imported = datetime(2024, 3, 1, 7, 38)
    res = resolve_date_time_reported(existing=existing, imported_dt=imported)
    assert res.set_origin is True
    assert res.atl_date_time_reported == imported
    assert res.origin_date == date(2024, 3, 1)
    assert res.origin_time == time(7, 38)


def test_scenario_2_existing_origin_not_overwritten_by_import():
    existing = SimpleNamespace(
        origin_date=date(2024, 1, 15),
        origin_time=time(9, 0),
    )
    imported = datetime(2024, 3, 1, 7, 38)
    res = resolve_date_time_reported(existing=existing, imported_dt=imported)
    assert res.set_origin is False
    assert res.atl_date_time_reported == datetime(2024, 1, 15, 9, 0)
    assert res.origin_date is None
    assert res.origin_time is None


def test_scenario_1_new_insert_with_import():
    res = resolve_date_time_reported(
        existing=None,
        imported_dt=datetime(2024, 3, 1, 7, 38),
    )
    assert res.set_origin is True
    assert res.origin_date == date(2024, 3, 1)


def test_validate_empty_reported_without_origin_errors():
    validated = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        atl_date_time_reported=None,
        atl_date_time_reported_provided=True,
        atl_date_time_reported_issue="empty",
    )
    refs = AtlImportReferences(existing_by_sequence={})
    errors = validate_date_time_reported_mapping(
        [(2, validated)],
        refs,
        raw_records=[{"sequence_no": "001", "atl_date_time_reported": None}],
    )
    assert len(errors) == 1
    assert errors[0]["column"] == "Date Time Reported"


def test_validate_empty_reported_with_existing_origin_ok():
    validated = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        atl_date_time_reported=None,
        atl_date_time_reported_provided=True,
        atl_date_time_reported_issue="empty",
    )
    existing = SimpleNamespace(
        origin_date=date(2024, 1, 15),
        origin_time=time(9, 0),
    )
    refs = AtlImportReferences(existing_by_sequence={"001": existing})
    errors = validate_date_time_reported_mapping([(2, validated)], refs)
    assert errors == []


def test_validate_skips_when_column_not_provided():
    validated = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        atl_date_time_reported_provided=False,
        atl_date_time_reported_issue=None,
    )
    refs = AtlImportReferences(existing_by_sequence={})
    errors = validate_date_time_reported_mapping([(2, validated)], refs)
    assert errors == []
