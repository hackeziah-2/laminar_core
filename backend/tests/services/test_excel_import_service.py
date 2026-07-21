"""Service-layer tests for Excel import orchestration."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError as AppValidationError
from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftImportSchema
from app.services.excel_import.config import ExcelImportConfig
from app.services.excel_import.reader import read_upload_records
from app.services.excel_import_service import ExcelImportService
from app.services.excel_import.parsers import (
    coerce_import_float,
    is_spreadsheet_empty,
    parse_import_date,
    parse_import_origin_date,
    sanitize_spreadsheet_value,
)
from tests.factories.import_files import aircraft_csv_bytes


class _MockUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
async def test_read_upload_records_parses_tab_separated_csv():
    """Tab-separated CSV exports (common from Excel paste) parse into columns."""
    from app.constants.ad_work_order_excel_import import AD_WORK_ORDER_EXCEL_COLUMN_MAPPING

    tsv = (
        "WO NUMBER\tLAST DONE AFTT\tLAST DONE TACH\tLAST DONE DATE\t"
        "NEXT DUE AFTT\tNEXT DUE TACH\tATL REF\n"
        "WO-1\t6080.1\t6079.5\t6/5/2023\t6180.1\t6179.5\tATL-1\n"
    )
    file = _MockUploadFile("ad-wo.csv", tsv.encode("utf-8"))
    rows = await read_upload_records(
        file,
        column_mapping=AD_WORK_ORDER_EXCEL_COLUMN_MAPPING,
    )
    assert rows == [
        {
            "work_order_number": "WO-1",
            "last_done_aftt": 6080.1,
            "last_done_tach": 6079.5,
            "last_done_date": "6/5/2023",
            "next_due_aftt": 6180.1,
            "next_due_tach": 6179.5,
            "atl_ref": "ATL-1",
        }
    ]


@pytest.mark.asyncio
async def test_read_upload_records_rejects_invalid_extension():
    """2. Validation — reader raises on bad extension."""
    file = _MockUploadFile("data.txt", b"x")
    with pytest.raises(AppValidationError, match="file only"):
        await read_upload_records(file)


@pytest.mark.asyncio
async def test_dry_run_does_not_persist(db_session: AsyncSession):
    """9. Transaction — dry_run leaves database empty."""
    config = ExcelImportConfig(
        model=Aircraft,
        schema=AircraftImportSchema,
        unique_fields=["registration", "msn"],
        hook_key="aircraft",
        dry_run=True,
    )
    file = _MockUploadFile("aircraft.csv", aircraft_csv_bytes())
    result = await ExcelImportService.run(file, db_session, config)
    assert result["status"] == "dry-run"

    count = await db_session.execute(select(Aircraft))
    assert len(count.scalars().all()) == 0


@pytest.mark.asyncio
async def test_import_success_persists_row(db_session: AsyncSession):
    """1. Success — commit inserts aircraft."""
    config = ExcelImportConfig(
        model=Aircraft,
        schema=AircraftImportSchema,
        unique_fields=["registration", "msn"],
        hook_key="aircraft",
        dry_run=False,
        audit_account_id=None,
    )
    file = _MockUploadFile("aircraft.csv", aircraft_csv_bytes())
    result = await ExcelImportService.run(file, db_session, config)
    assert result["status"] == "success"
    assert result["inserted"] == 1

    row = (
        await db_session.execute(
            select(Aircraft).where(Aircraft.registration == "IMP-001")
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.msn == "MSN-IMP-001"


@pytest.mark.asyncio
async def test_import_duplicate_row_in_file_reports_errors(db_session: AsyncSession):
    """6. Duplicate — identical rows in one file are skipped on write; dry_run counts both."""
    duplicate_rows = [
        {
            "registration": "DUP-001",
            "model": "172",
            "msn": "DUP-MSN-1",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
        {
            "registration": "DUP-001",
            "model": "172",
            "msn": "DUP-MSN-1",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
    ]
    config = ExcelImportConfig(
        model=Aircraft,
        schema=AircraftImportSchema,
        unique_fields=["registration", "msn"],
        hook_key="aircraft",
        dry_run=False,
    )
    file = _MockUploadFile("aircraft.csv", aircraft_csv_bytes(duplicate_rows))
    result = await ExcelImportService.run(file, db_session, config)
    assert result["status"] == "success"
    rows = (
        await db_session.execute(
            select(Aircraft).where(Aircraft.registration == "DUP-001")
        )
    ).scalars().all()
    assert len(rows) == 1


def test_parse_import_origin_date_excel_serial():
    """10. Edge case — Excel serial date integer."""
    parsed = parse_import_origin_date(45292)
    assert parsed is not None
    assert hasattr(parsed, "year")


def test_parse_import_date_string_formats():
    """LDND date strings: 17-Aug-23 and 8/17/2023."""
    from datetime import date

    assert parse_import_date("17-Aug-23") == date(2023, 8, 17)
    assert parse_import_date("8/17/2023") == date(2023, 8, 17)


def test_spreadsheet_empty_sentinels():
    """pandas NaT/NaN from Excel must not reach the database layer."""
    import math

    import pandas as pd

    assert is_spreadsheet_empty(pd.NaT) is True
    assert is_spreadsheet_empty(float("nan")) is True
    assert sanitize_spreadsheet_value(pd.NaT) is None
    assert coerce_import_float(float("nan")) is None
    assert parse_import_date(pd.NaT) is None
    assert parse_import_date(float("nan")) is None
    assert not math.isnan(coerce_import_float(12.0) or 0)


def test_coerce_import_float_strips_internal_spaces():
    assert coerce_import_float("17588. 11") == 17588.11
    assert coerce_import_float(" 12,345. 6 ") == 12345.6
    assert coerce_import_float("not-a-number") is None


def test_coerce_import_decimal_preserves_fractional_digits():
    from decimal import Decimal

    from app.services.excel_import.parsers import coerce_import_decimal

    assert coerce_import_decimal("123.4567") == Decimal("123.4567")
    assert coerce_import_decimal("45.10") == Decimal("45.10")
    assert coerce_import_decimal("80.5") == Decimal("80.5")
    assert coerce_import_decimal("17588. 11") == Decimal("17588.11")


def test_import_schema_preserves_exact_decimal_strings():
    from decimal import Decimal

    from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema

    row = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        tachometer_end="123.4567",
        engine_tso="45.10",
        propeller_tsn="80.5",
        airframe_aftt="502.5000",
    )
    assert row.tachometer_end == Decimal("123.4567")
    assert row.engine_tso == Decimal("45.10")
    assert row.propeller_tsn == Decimal("80.5")
    assert row.airframe_aftt == Decimal("502.5000")


def test_api_read_schema_does_not_round_imported_values():
    from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogApiRead

    read = AircraftTechnicalLogApiRead(
        id=1,
        aircraft_fk=1,
        sequence_no="001",
        airframe_aftt=502.567,
        engine_tso=300.256,
        propeller_tsn=150.5123,
        engine_tsn="1200.50",
    )
    assert read.airframe_aftt == 502.567
    assert read.engine_tso == 300.256
    assert read.propeller_tsn == 150.5123
    assert read.engine_tsn == "1200.50"


def test_import_schema_accepts_spaced_numeric_strings():
    from decimal import Decimal

    from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema

    row = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        sequence_no="001",
        propeller_tsn="17588. 11",
        engine_tsn="17588. 11",
        airframe_aftt="100. 5",
    )
    assert row.propeller_tsn == Decimal("17588.11")
    assert row.engine_tsn == "17588.11"
    assert row.airframe_aftt == Decimal("100.5")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("001", "001"),
        ("ATL-001", "001"),
        ("QM-001", "QM-001"),
        ("ATL-SEQ-A2", "SEQ-A2"),
        ("SEQ-A2", "SEQ-A2"),
        (10001.0, "10001"),
        (42, "42"),
    ],
)
def test_import_schema_accepts_string_sequence_no(raw, expected):
    from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema

    row = AircraftTechnicalLogImportSchema(aircraft_fk=1, sequence_no=raw)
    assert row.sequence_no == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PRE EGR", "EGR"),
        ("PSF EGR", "EGR"),
        ("POST EGR", "EGR"),
        ("EGR", "EGR"),
        (" pre egr ", "EGR"),
        ("PSF-EGR", "EGR"),
        ("TR", "TR"),
        ("PRE", "PRF"),
        ("PST", "PSF"),
        ("BLANK", None),
        ("CANCELLED FLT", "CANCELLED_FLT"),
        ("cancelled flt", "CANCELLED_FLT"),
        ("CANCELLED_FLT", "CANCELLED_FLT"),
    ],
)
def test_normalize_import_nature_of_flight(raw, expected):
    from app.services.excel_import.parsers import normalize_import_nature_of_flight

    assert normalize_import_nature_of_flight(raw) == expected
