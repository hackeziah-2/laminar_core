"""Tests for Origin Date / Origin Time Excel import parsing."""
from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd
import pytest

from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.excel_import.parsers import (
    SpreadsheetParseError,
    parse_excel_datetime,
    parse_excel_time,
    resolve_origin_date_time,
)
from app.services.excel_import.row_builder import build_row_for_schema, schema_field_names
from app.services.excel_import.hooks.base import ImportHook


class _NoOpHook(ImportHook):
    def preprocess_records(self, records):
        return records


def test_combined_datetime_splits_date_and_time():
    parsed_date, extracted_time = parse_excel_datetime("2026-01-06 08:30:00")
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(8, 30, 0)

    origin_date, origin_time = resolve_origin_date_time("2026-01-06 08:30:00", None)
    assert origin_date == date(2026, 1, 6)
    assert origin_time == time(8, 30, 0)


def test_midnight_datetime_keeps_zero_time():
    parsed_date, extracted_time = parse_excel_datetime("2026-01-06 00:00:00")
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(0, 0, 0)

    origin_date, origin_time = resolve_origin_date_time("2026-01-06 00:00:00", None)
    assert origin_date == date(2026, 1, 6)
    assert origin_time == time(0, 0, 0)


def test_date_only_has_null_time():
    parsed_date, extracted_time = parse_excel_datetime("2026-01-06")
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time is None

    origin_date, origin_time = resolve_origin_date_time("2026-01-06", None)
    assert origin_date == date(2026, 1, 6)
    assert origin_time is None


def test_slash_datetime_format():
    parsed_date, extracted_time = parse_excel_datetime("06/01/2026 08:30:00")
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(8, 30, 0)


def test_mon_abbreviation_datetime_format():
    parsed_date, extracted_time = parse_excel_datetime("06-Jan-26 0830")
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(8, 30)


def test_python_datetime_object():
    value = datetime(2026, 1, 6, 8, 30, 0)
    parsed_date, extracted_time = parse_excel_datetime(value)
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(8, 30, 0)


def test_python_date_object():
    parsed_date, extracted_time = parse_excel_datetime(date(2026, 1, 6))
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time is None


def test_pandas_timestamp():
    ts = pd.Timestamp("2026-01-06 08:30:00")
    parsed_date, extracted_time = parse_excel_datetime(ts)
    assert parsed_date == date(2026, 1, 6)
    assert extracted_time == time(8, 30, 0)


def test_separate_origin_time_column():
    origin_date, origin_time = resolve_origin_date_time("2026-01-06", "09:15")
    assert origin_date == date(2026, 1, 6)
    assert origin_time == time(9, 15)


def test_explicit_origin_time_overrides_extracted_time():
    origin_date, origin_time = resolve_origin_date_time(
        "2026-01-06 08:30:00",
        "10:00",
    )
    assert origin_date == date(2026, 1, 6)
    assert origin_time == time(10, 0)


def test_blank_origin_date_and_time():
    assert parse_excel_datetime("") == (None, None)
    assert parse_excel_datetime(None) == (None, None)
    assert parse_excel_time("") is None
    assert parse_excel_time(None) is None
    assert resolve_origin_date_time("", "") == (None, None)


def test_nan_and_nat_values():
    assert parse_excel_datetime(float("nan")) == (None, None)
    assert parse_excel_datetime(pd.NaT) == (None, None)
    assert parse_excel_time(float("nan")) is None
    assert parse_excel_time(pd.NaT) is None
    assert resolve_origin_date_time(float("nan"), pd.NaT) == (None, None)


def test_invalid_origin_date_raises():
    with pytest.raises(SpreadsheetParseError) as exc_info:
        parse_excel_datetime("31/02/2026")
    assert exc_info.value.field == "origin_date"


def test_invalid_origin_time_raises():
    with pytest.raises(SpreadsheetParseError) as exc_info:
        parse_excel_time("25:99")
    assert exc_info.value.field == "origin_time"


def test_build_row_for_schema_resolves_origin_fields():
    schema_fields = schema_field_names(AircraftTechnicalLogImportSchema)
    row = build_row_for_schema(
        {"origin_date": "2026-01-06 08:30:00"},
        schema_fields=schema_fields,
        inject_fields={"aircraft_fk": 1, "sequence_no": "001"},
        hook=_NoOpHook(),
    )
    assert row["origin_date"] == date(2026, 1, 6)
    assert row["origin_time"] == time(8, 30, 0)


def test_import_schema_accepts_combined_origin_datetime():
    row = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        origin_date=date(2026, 1, 6),
        origin_time=time(8, 30, 0),
    )
    assert row.origin_date == date(2026, 1, 6)
    assert row.origin_time == time(8, 30, 0)


def test_excel_serial_date_without_fraction_is_date_only():
    parsed_date, extracted_time = parse_excel_datetime(45292)
    assert parsed_date == date(2024, 1, 1)
    assert extracted_time is None
