"""Tests for ATL import validation and atomic all-or-nothing behavior."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_batch import AtlBatch
from app.services.atl_import_validation import validate_atl_import_records
from tests.conftest import TestSessionLocal


async def _seed_aircraft_and_batch() -> tuple[int, int]:
    async with TestSessionLocal() as session:
        ac = Aircraft(
            registration="ATL-VAL-1",
            model="172",
            msn="ATL-VAL-MSN",
            base="Base",
            ownership="Owner",
            status="Active",
        )
        session.add(ac)
        await session.flush()
        batch = AtlBatch(name="Validation Batch", description="pytest")
        session.add(batch)
        await session.commit()
        await session.refresh(ac)
        await session.refresh(batch)
        return ac.id, batch.id


@pytest.mark.asyncio
async def test_validate_atl_import_records_collects_all_errors(db_session):
    async with TestSessionLocal() as session:
        ac = Aircraft(
            registration="ATL-VAL-UNIT",
            model="172",
            msn="ATL-VAL-UNIT-MSN",
            base="Base",
            ownership="Owner",
            status="Active",
        )
        session.add(ac)
        await session.flush()
        batch = AtlBatch(name="Validation Unit Batch", description="pytest")
        session.add(batch)
        await session.commit()
        await session.refresh(ac)
        await session.refresh(batch)
        aircraft_id, batch_id = ac.id, batch.id

    records = [
        {"sequence_no": "", "number_of_landings": "ABC"},
        {"sequence_no": "002", "origin_date": "31/02/2026"},
    ]
    inject_fields = {"aircraft_fk": aircraft_id, "atl_batch_fk": batch_id}

    async with TestSessionLocal() as session:
        validated, errors = await validate_atl_import_records(
            session, records, inject_fields=inject_fields
        )

    assert validated == []
    assert len(errors) >= 2
    rows = {e["row"] for e in errors}
    assert 2 in rows
    assert 3 in rows
    for err in errors:
        assert "column" in err
        assert "value" in err
        assert "error" in err


def test_atl_sync_import_atomic_on_validation_errors(
    client_with_maintenance_import_auth,
):
    """Invalid rows must not persist any ATL records."""
    aircraft_id, batch_id = asyncio.run(_seed_aircraft_and_batch())
    csv_body = (
        b"sequence_no,number_of_landings,origin_date\n"
        b"001,5,01/01/2026\n"
        b"002,ABC,31/02/2026\n"
    )
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["message"] == "The file contains validation errors. No records were imported."
    assert len(body["errors"]) >= 1
    assert body["error_report"]
    assert "No records were imported" in body["error_report"]

    async def _count_rows() -> int:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(AircraftTechnicalLog).where(
                    AircraftTechnicalLog.aircraft_fk == aircraft_id,
                    AircraftTechnicalLog.atl_batch_fk == batch_id,
                )
            )
            return len(result.scalars().all())

    assert asyncio.run(_count_rows()) == 0


def test_atl_sync_import_returns_summary(
    client_with_maintenance_import_auth,
):
    aircraft_id, batch_id = asyncio.run(_seed_aircraft_and_batch())
    csv_body = b"sequence_no,tachometer_start,tachometer_end\n001,1,2\n"
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["total_rows"] == 1
    assert body["imported_rows"] == 1
    assert body["processing_time_ms"] is not None


def test_atl_sync_import_succeeds_when_all_rows_valid(
    client_with_maintenance_import_auth,
):
    aircraft_id, batch_id = asyncio.run(_seed_aircraft_and_batch())
    csv_body = b"sequence_no,tachometer_start,tachometer_end\n001,1,2\n002,2,3\n"
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    async def _count_rows() -> int:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(AircraftTechnicalLog).where(
                    AircraftTechnicalLog.aircraft_fk == aircraft_id,
                    AircraftTechnicalLog.atl_batch_fk == batch_id,
                )
            )
            return len(result.scalars().all())

    assert asyncio.run(_count_rows()) == 2
