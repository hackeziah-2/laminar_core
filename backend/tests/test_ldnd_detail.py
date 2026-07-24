"""Tests for GET /api/v1/aircraft/{aircraft_id}/ldnd-detail."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.models.atl_monitoring import LDNDMonitoring
from app.models.fleet_daily_update import FleetDailyUpdate
from tests.conftest import TestSessionLocal


def _create_aircraft(client: TestClient, registration: str) -> int:
    payload = {
        "registration": registration,
        "model": "172",
        "msn": f"MSN-{registration}",
        "base": "Test Base",
        "ownership": "Test Owner",
        "status": "Active",
    }
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_ldnd(
    client: TestClient,
    aircraft_id: int,
    *,
    inspection_type: str = "100-Hour Inspection",
    unit: str = "HRS",
    last_done_tach_due: Optional[float] = 1500.5,
) -> dict:
    response = client.post(
        f"/api/v1/aircraft/{aircraft_id}/ldnd-monitoring/",
        json={
            "aircraft_fk": aircraft_id,
            "inspection_type": inspection_type,
            "unit": unit,
            "last_done_tach_due": last_done_tach_due,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_tach_time_eod(client: TestClient, aircraft_id: int, tach: float) -> None:
    response = client.patch(
        f"/api/v1/aircraft/{aircraft_id}/fleet-daily-update",
        json={"tach_time_eod": tach},
    )
    assert response.status_code == 200, response.text


def _soft_delete_fleet_daily_update(aircraft_id: int) -> None:
    async def _run() -> None:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(FleetDailyUpdate).where(
                    FleetDailyUpdate.aircraft_fk == aircraft_id
                )
            )
            row = result.scalar_one_or_none()
            assert row is not None
            row.is_deleted = True
            session.add(row)
            await session.commit()

    asyncio.run(_run())


def _bump_ldnd_created_at(ldnd_id: int, created_at: datetime) -> None:
    async def _run() -> None:
        async with TestSessionLocal() as session:
            await session.execute(
                update(LDNDMonitoring)
                .where(LDNDMonitoring.id == ldnd_id)
                .values(created_at=created_at)
            )
            await session.commit()

    asyncio.run(_run())


def test_ldnd_detail_with_both_records(client: TestClient):
    aircraft_id = _create_aircraft(client, "LDND-DET-001")
    _create_ldnd(
        client,
        aircraft_id,
        inspection_type="100-Hour Inspection",
        unit="HRS",
        last_done_tach_due=1500.5,
    )
    _set_tach_time_eod(client, aircraft_id, 1425.7)

    response = client.get(f"/api/v1/aircraft/{aircraft_id}/ldnd-detail")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["aircraft_id"] == aircraft_id
    assert body["next_inspection"] == 1500.5
    assert body["current_tach"] == 1425.7
    assert body["last_updated"]["inspection_type"] == "100-Hour Inspection"
    assert body["last_updated"]["unit"] == "HRS"
    assert body["last_updated"]["display_value"] == "100-Hour Inspection - HRS"
    assert body["last_updated"]["updated_at"] is not None
    # Parseable timestamp (Postgres returns TZ-aware; SQLite tests may be naive)
    datetime.fromisoformat(body["last_updated"]["updated_at"])


def test_ldnd_detail_without_ldnd_record(client: TestClient):
    aircraft_id = _create_aircraft(client, "LDND-DET-002")
    _set_tach_time_eod(client, aircraft_id, 1100.0)

    response = client.get(f"/api/v1/aircraft/{aircraft_id}/ldnd-detail")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["aircraft_id"] == aircraft_id
    assert body["next_inspection"] is None
    assert body["last_updated"] == {
        "inspection_type": None,
        "unit": None,
        "display_value": None,
        "updated_at": None,
    }
    assert body["current_tach"] == 1100.0


def test_ldnd_detail_without_fleet_daily_update(client: TestClient):
    aircraft_id = _create_aircraft(client, "LDND-DET-003")
    _create_ldnd(
        client,
        aircraft_id,
        inspection_type="Annual Inspection",
        unit="HRS",
        last_done_tach_due=2000.0,
    )
    _soft_delete_fleet_daily_update(aircraft_id)

    response = client.get(f"/api/v1/aircraft/{aircraft_id}/ldnd-detail")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["aircraft_id"] == aircraft_id
    assert body["next_inspection"] == 2000.0
    assert body["last_updated"]["inspection_type"] == "Annual Inspection"
    assert body["last_updated"]["unit"] == "HRS"
    assert body["last_updated"]["display_value"] == "Annual Inspection - HRS"
    assert body["last_updated"]["updated_at"] is not None
    assert body["current_tach"] is None


def test_ldnd_detail_without_either_record(client: TestClient):
    aircraft_id = _create_aircraft(client, "LDND-DET-004")
    _soft_delete_fleet_daily_update(aircraft_id)

    response = client.get(f"/api/v1/aircraft/{aircraft_id}/ldnd-detail")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body == {
        "aircraft_id": aircraft_id,
        "next_inspection": None,
        "last_updated": {
            "inspection_type": None,
            "unit": None,
            "display_value": None,
            "updated_at": None,
        },
        "current_tach": None,
    }


def test_ldnd_detail_selects_latest_ldnd_record(client: TestClient):
    aircraft_id = _create_aircraft(client, "LDND-DET-005")
    older = _create_ldnd(
        client,
        aircraft_id,
        inspection_type="50-Hour Inspection",
        unit="HRS",
        last_done_tach_due=1000.0,
    )
    newer = _create_ldnd(
        client,
        aircraft_id,
        inspection_type="100-Hour Inspection",
        unit="CYCLES",
        last_done_tach_due=1500.5,
    )
    base = datetime.now(ZoneInfo("Asia/Manila"))
    _bump_ldnd_created_at(older["id"], base - timedelta(hours=2))
    _bump_ldnd_created_at(newer["id"], base - timedelta(hours=1))
    _set_tach_time_eod(client, aircraft_id, 1425.7)

    response = client.get(f"/api/v1/aircraft/{aircraft_id}/ldnd-detail")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["next_inspection"] == 1500.5
    assert body["last_updated"]["inspection_type"] == "100-Hour Inspection"
    assert body["last_updated"]["unit"] == "CYCLES"
    assert body["last_updated"]["display_value"] == "100-Hour Inspection - CYCLES"
    assert body["current_tach"] == 1425.7


def test_ldnd_detail_excludes_other_aircraft_records(client: TestClient):
    aircraft_a = _create_aircraft(client, "LDND-DET-006A")
    aircraft_b = _create_aircraft(client, "LDND-DET-006B")

    _create_ldnd(
        client,
        aircraft_a,
        inspection_type="A Inspection",
        unit="HRS",
        last_done_tach_due=1111.1,
    )
    _set_tach_time_eod(client, aircraft_a, 1010.1)

    _create_ldnd(
        client,
        aircraft_b,
        inspection_type="B Inspection",
        unit="CYCLES",
        last_done_tach_due=2222.2,
    )
    _set_tach_time_eod(client, aircraft_b, 2020.2)

    response_a = client.get(f"/api/v1/aircraft/{aircraft_a}/ldnd-detail")
    assert response_a.status_code == 200, response_a.text
    body_a = response_a.json()
    assert body_a["aircraft_id"] == aircraft_a
    assert body_a["next_inspection"] == 1111.1
    assert body_a["last_updated"]["inspection_type"] == "A Inspection"
    assert body_a["last_updated"]["unit"] == "HRS"
    assert body_a["current_tach"] == 1010.1

    response_b = client.get(f"/api/v1/aircraft/{aircraft_b}/ldnd-detail")
    assert response_b.status_code == 200, response_b.text
    body_b = response_b.json()
    assert body_b["aircraft_id"] == aircraft_b
    assert body_b["next_inspection"] == 2222.2
    assert body_b["last_updated"]["inspection_type"] == "B Inspection"
    assert body_b["last_updated"]["unit"] == "CYCLES"
    assert body_b["current_tach"] == 2020.2


def test_ldnd_detail_invalid_aircraft_returns_404(client: TestClient):
    response = client.get("/api/v1/aircraft/999999/ldnd-detail")
    assert response.status_code == 404
    assert response.json() == {"detail": "Aircraft not found"}
