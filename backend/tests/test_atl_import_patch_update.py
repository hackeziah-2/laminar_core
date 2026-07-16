"""ATL Excel import PATCH-style update: empty cells preserve existing DB values."""
from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.aircraft_techinical_log import WorkStatus
from app.repository.atl_import import (
    _is_patchable_import_value,
    _model_payload_from_validated,
    bulk_upsert_atl_import_rows,
)
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.atl_import_references import AtlImportReferences
from app.services.atl_import_validation import validate_atl_row_schema


def test_is_patchable_import_value():
    assert _is_patchable_import_value("Cebu") is True
    assert _is_patchable_import_value(0) is True
    assert _is_patchable_import_value(False) is True
    assert _is_patchable_import_value(None) is False
    assert _is_patchable_import_value("") is False


def test_patch_payload_skips_empty_and_missing_fields():
    validated = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        atl_batch_fk=2,
        sequence_no="001",
        origin_date=None,
        origin_time=time(9, 30),
        destination_station="Cebu",
        # pilot_fk omitted → must not appear as an update key when patched
    )
    patch = _model_payload_from_validated(validated, patch=True)

    assert patch["sequence_no"] == "001"
    assert patch["origin_time"] == time(9, 30)
    assert patch["destination_station"] == "Cebu"
    assert "origin_date" not in patch
    assert "pilot_fk" not in patch
    assert "work_status" not in patch


def test_full_payload_keeps_nones_for_insert():
    validated = AircraftTechnicalLogImportSchema(
        aircraft_fk=1,
        atl_batch_fk=2,
        sequence_no="001",
        origin_date=None,
        origin_time=time(9, 30),
    )
    full = _model_payload_from_validated(validated, patch=False)
    assert full["origin_time"] == time(9, 30)
    assert "origin_date" in full
    assert full["origin_date"] is None


def test_empty_excel_work_status_does_not_force_for_review_on_schema():
    validated, errors = validate_atl_row_schema(
        {"sequence_no": "001", "work_status": ""},
        excel_row=2,
        inject_fields={"aircraft_fk": 1, "atl_batch_fk": 2},
    )
    assert errors == []
    assert validated is not None
    assert validated.work_status is None


def test_explicit_work_status_still_imported():
    validated, errors = validate_atl_row_schema(
        {"sequence_no": "001", "work_status": "APPROVED"},
        excel_row=2,
        inject_fields={"aircraft_fk": 1, "atl_batch_fk": 2},
    )
    assert errors == []
    assert validated is not None
    assert validated.work_status == WorkStatus.APPROVED
    patch = _model_payload_from_validated(validated, patch=True)
    assert patch["work_status"] == WorkStatus.APPROVED


@pytest.mark.asyncio
async def test_bulk_upsert_patches_only_non_empty_fields():
    existing = SimpleNamespace(
        id=10,
        sequence_no="001",
        origin_date=date(2026, 7, 1),
        origin_time=time(8, 0),
        destination_station="Manila",
        pilot_fk=99,
        work_status=WorkStatus.APPROVED,
        is_deleted=False,
        atl_date_time_reported=None,
    )
    validated, errors = validate_atl_row_schema(
        {
            "sequence_no": "001",
            "origin_date": "",
            "origin_time": "09:30",
            "destination_station": "Cebu",
            # pilot_fk / work_status not in file
        },
        excel_row=2,
        inject_fields={"aircraft_fk": 1, "atl_batch_fk": 2},
    )
    assert errors == []
    assert validated is not None

    session = MagicMock()
    session.flush = AsyncMock()
    references = AtlImportReferences(
        existing_by_sequence={"001": existing},
        valid_account_ids=set(),
    )

    inserted, updated = await bulk_upsert_atl_import_rows(
        session,
        [(2, validated)],
        references=references,
        audit_account_id=None,
    )

    assert inserted == 0
    assert updated == 1
    assert existing.origin_date == date(2026, 7, 1)
    assert existing.origin_time == time(9, 30)
    assert existing.destination_station == "Cebu"
    assert existing.pilot_fk == 99
    assert existing.work_status == WorkStatus.APPROVED


@pytest.mark.asyncio
async def test_bulk_upsert_insert_defaults_work_status_for_review():
    validated, errors = validate_atl_row_schema(
        {"sequence_no": "002", "destination_station": "Cebu"},
        excel_row=2,
        inject_fields={"aircraft_fk": 1, "atl_batch_fk": 2},
    )
    assert errors == []
    assert validated is not None

    created: list = []

    class _FakeSession:
        def add(self, obj):
            created.append(obj)

        async def flush(self):
            for obj in created:
                if getattr(obj, "id", None) is None:
                    obj.id = 1

    references = AtlImportReferences(existing_by_sequence={}, valid_account_ids=set())
    inserted, updated = await bulk_upsert_atl_import_rows(
        _FakeSession(),
        [(2, validated)],
        references=references,
        audit_account_id=None,
    )

    assert inserted == 1
    assert updated == 0
    assert len(created) == 1
    assert created[0].work_status == WorkStatus.FOR_REVIEW
    assert created[0].destination_station == "Cebu"
