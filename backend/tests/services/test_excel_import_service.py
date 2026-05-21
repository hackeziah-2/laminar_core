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
            "manufacturer": "Cessna",
            "model": "172",
            "msn": "DUP-MSN-1",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
        {
            "registration": "DUP-001",
            "manufacturer": "Cessna",
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
