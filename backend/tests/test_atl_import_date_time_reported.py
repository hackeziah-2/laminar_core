"""Unit tests for ATL Date Time Reported import mapping (origin_*)."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace

from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.atl_import_date_time_reported import (
    as_naive_ph,
    combine_date_and_time,
    resolve_date_time_reported,
    try_parse_atl_date_time_reported,
)
from app.services.atl_import_references import AtlImportReferences
from app.services.atl_import_validation import validate_date_time_reported_mapping


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
