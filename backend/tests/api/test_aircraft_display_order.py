"""API tests for shared aircraft display_order (Fleet Profile + Fleet Daily Update)."""
from __future__ import annotations

import asyncio
import json
from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.aircraft import Aircraft
from app.models.fleet_daily_update import FleetDailyUpdate
from app.repository.aircraft import (
    list_aircraft,
    place_restored_aircraft_at_end,
)
from app.repository.fleet_daily_update import list_fleet_daily_updates
from tests.conftest import TestSessionLocal
from tests.factories.import_files import aircraft_csv_bytes


def _create_aircraft(client: TestClient, registration: str, msn: str) -> dict:
    response = client.post(
        "/api/v1/aircraft/",
        data={
            "json_data": json.dumps(
                {
                    "registration": registration,
                    "model": "172",
                    "msn": msn,
                    "base": "Base",
                    "ownership": "Owner",
                    "status": "Active",
                }
            )
        },
        files={},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _fleet_profile_order() -> Tuple[List[str], List[int]]:
    async with TestSessionLocal() as session:
        items, _ = await list_aircraft(session, limit=50, offset=0)
        return (
            [i.registration for i in items],
            [i.display_order for i in items],
        )


async def _fleet_daily_order() -> Tuple[List[str], List[int]]:
    async with TestSessionLocal() as session:
        items, _ = await list_fleet_daily_updates(session, limit=50, offset=0)
        regs = []
        orders = []
        for item in items:
            regs.append(item.aircraft.registration)
            orders.append(item.aircraft.display_order)
        return regs, orders


def test_aircraft_reorder_success_shared_by_profile_and_daily_update(client: TestClient):
    """Successful reorder; Fleet Profile and Fleet Daily Update share the same order."""
    a = _create_aircraft(client, "RP-2323", "MSN-2323")
    b = _create_aircraft(client, "RP-12", "MSN-12")
    c = _create_aircraft(client, "RP-C603", "MSN-C603")

    payload = {
        "items": [
            {"aircraft_id": c["id"], "display_order": 1},
            {"aircraft_id": a["id"], "display_order": 2},
            {"aircraft_id": b["id"], "display_order": 3},
        ]
    }
    response = client.put("/api/v1/aircraft/reorder", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["registration"] for item in body["items"]] == [
        "RP-C603",
        "RP-2323",
        "RP-12",
    ]
    assert [item["display_order"] for item in body["items"]] == [1, 2, 3]

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["RP-C603", "RP-2323", "RP-12"]
    assert orders == [1, 2, 3]

    fdu_regs, fdu_orders = asyncio.run(_fleet_daily_order())
    assert fdu_regs == regs
    assert fdu_orders == orders

    # Persists on retrieve again
    paged = client.get("/api/v1/aircraft/paged?page_size=50&page=1")
    assert paged.status_code == 200
    assert [i["registration"] for i in paged.json()["items"]] == [
        "RP-C603",
        "RP-2323",
        "RP-12",
    ]
    assert [i["display_order"] for i in paged.json()["items"]] == [1, 2, 3]


def test_aircraft_reorder_rejects_duplicate_ids(client: TestClient):
    a = _create_aircraft(client, "DUP-ID-A", "DUP-ID-A-MSN")
    response = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": 1},
                {"aircraft_id": a["id"], "display_order": 2},
            ]
        },
    )
    assert response.status_code == 400
    assert "Duplicate record IDs" in response.json()["detail"]


def test_aircraft_reorder_rejects_missing_ids(client: TestClient):
    a = _create_aircraft(client, "MISS-A", "MISS-A-MSN")
    response = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": 1},
                {"aircraft_id": 999999, "display_order": 2},
            ]
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_aircraft_reorder_rejects_invalid_and_duplicate_display_order(client: TestClient):
    a = _create_aircraft(client, "BAD-ORD-A", "BAD-ORD-A-MSN")
    b = _create_aircraft(client, "BAD-ORD-B", "BAD-ORD-B-MSN")

    zero = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": 0},
                {"aircraft_id": b["id"], "display_order": 1},
            ]
        },
    )
    assert zero.status_code == 422

    negative = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": -1},
                {"aircraft_id": b["id"], "display_order": 1},
            ]
        },
    )
    assert negative.status_code == 422

    dup_order = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": 1},
                {"aircraft_id": b["id"], "display_order": 1},
            ]
        },
    )
    assert dup_order.status_code == 400
    assert "Duplicate display_order" in dup_order.json()["detail"]

    non_sequential = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": a["id"], "display_order": 1},
                {"aircraft_id": b["id"], "display_order": 3},
            ]
        },
    )
    assert non_sequential.status_code == 400
    assert "sequential" in non_sequential.json()["detail"].lower()


def test_aircraft_reorder_rolls_back_when_one_item_invalid(client: TestClient):
    a = _create_aircraft(client, "RB-A", "RB-A-MSN")
    b = _create_aircraft(client, "RB-B", "RB-B-MSN")
    c = _create_aircraft(client, "RB-C", "RB-C-MSN")

    response = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": c["id"], "display_order": 1},
                {"aircraft_id": a["id"], "display_order": 2},
                {"aircraft_id": 999999, "display_order": 3},
            ]
        },
    )
    assert response.status_code == 404

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["RB-A", "RB-B", "RB-C"]
    assert orders == [1, 2, 3]


@pytest.mark.no_auth
def test_aircraft_reorder_unauthorized(client: TestClient):
    response = client.put(
        "/api/v1/aircraft/reorder",
        json={"items": [{"aircraft_id": 1, "display_order": 1}]},
    )
    assert response.status_code == 401


def test_aircraft_create_appends_last_display_order(client: TestClient):
    _create_aircraft(client, "APP-A", "APP-A-MSN")
    _create_aircraft(client, "APP-B", "APP-B-MSN")
    created = _create_aircraft(client, "APP-NEW", "APP-NEW-MSN")
    assert created["display_order"] == 3

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["APP-A", "APP-B", "APP-NEW"]
    assert orders == [1, 2, 3]


def test_aircraft_delete_normalizes_remaining_display_order(client: TestClient):
    a = _create_aircraft(client, "DEL-A", "DEL-A-MSN")
    b = _create_aircraft(client, "DEL-B", "DEL-B-MSN")
    c = _create_aircraft(client, "DEL-C", "DEL-C-MSN")
    assert [a["display_order"], b["display_order"], c["display_order"]] == [1, 2, 3]

    deleted = client.delete(f"/api/v1/aircraft/{b['id']}")
    assert deleted.status_code == 204, deleted.text

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["DEL-A", "DEL-C"]
    assert orders == [1, 2]


def test_restored_aircraft_appended_to_bottom(client: TestClient):
    a = _create_aircraft(client, "RES-A", "RES-A-MSN")
    b = _create_aircraft(client, "RES-B", "RES-B-MSN")
    c = _create_aircraft(client, "RES-C", "RES-C-MSN")

    deleted = client.delete(f"/api/v1/aircraft/{b['id']}")
    assert deleted.status_code == 204

    async def _restore() -> None:
        async with TestSessionLocal() as session:
            row = (
                await session.execute(select(Aircraft).where(Aircraft.id == b["id"]))
            ).scalar_one()
            await place_restored_aircraft_at_end(session, row)
            await session.commit()

    asyncio.run(_restore())

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["RES-A", "RES-C", "RES-B"]
    assert orders == [1, 2, 3]
    assert a["id"] and c["id"]


def test_excel_import_order_preserved_and_partial_append(
    client_with_general_information_import_auth: TestClient,
    client: TestClient,
):
    """Excel row order is preserved; non-imported aircraft append afterward."""
    existing = _create_aircraft(client, "KEEP-EXISTING", "KEEP-EXISTING-MSN")

    rows = [
        {
            "registration": "IMP-C",
            "model": "172",
            "msn": "IMP-C-MSN",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
        {
            "registration": "IMP-A",
            "model": "172",
            "msn": "IMP-A-MSN",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
        {
            "registration": "IMP-B",
            "model": "172",
            "msn": "IMP-B-MSN",
            "base": "Base",
            "ownership": "Owner",
            "status": "Active",
        },
    ]
    resp = client_with_general_information_import_auth.post(
        "/api/v1/excel-data/aircraft/import",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(rows), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    regs, orders = asyncio.run(_fleet_profile_order())
    assert regs == ["IMP-C", "IMP-A", "IMP-B", "KEEP-EXISTING"]
    assert orders == [1, 2, 3, 4]
    assert existing["id"]

    fdu_regs, fdu_orders = asyncio.run(_fleet_daily_order())
    assert fdu_regs == regs
    assert fdu_orders == orders


def test_pagination_follows_global_display_order(client: TestClient):
    created = [
        _create_aircraft(client, f"PAGE-{i}", f"PAGE-{i}-MSN") for i in range(1, 5)
    ]
    # Reverse order via reorder
    payload = {
        "items": [
            {"aircraft_id": created[3]["id"], "display_order": 1},
            {"aircraft_id": created[2]["id"], "display_order": 2},
            {"aircraft_id": created[1]["id"], "display_order": 3},
            {"aircraft_id": created[0]["id"], "display_order": 4},
        ]
    }
    assert client.put("/api/v1/aircraft/reorder", json=payload).status_code == 200

    page1 = client.get("/api/v1/aircraft/paged?page_size=50&page=1")
    assert page1.status_code == 200
    regs = [i["registration"] for i in page1.json()["items"]]
    assert regs[:4] == ["PAGE-4", "PAGE-3", "PAGE-2", "PAGE-1"]

    async def _fdu_pages() -> Tuple[List[str], List[str]]:
        async with TestSessionLocal() as session:
            p1, _ = await list_fleet_daily_updates(session, limit=2, offset=0)
            p2, _ = await list_fleet_daily_updates(session, limit=2, offset=2)
            return (
                [i.aircraft.registration for i in p1],
                [i.aircraft.registration for i in p2],
            )

    fdu_page1, fdu_page2 = asyncio.run(_fdu_pages())
    assert fdu_page1 == ["PAGE-4", "PAGE-3"]
    assert fdu_page2 == ["PAGE-2", "PAGE-1"]


def test_reorder_does_not_modify_daily_update_maintenance_values(client: TestClient):
    a = _create_aircraft(client, "FDU-A", "FDU-A-MSN")
    b = _create_aircraft(client, "FDU-B", "FDU-B-MSN")

    async def _set_and_snapshot() -> Tuple[int, float, str]:
        async with TestSessionLocal() as session:
            fdu = (
                await session.execute(
                    select(FleetDailyUpdate).where(
                        FleetDailyUpdate.aircraft_fk == a["id"]
                    )
                )
            ).scalar_one()
            fdu.tach_time_eod = 1234.5
            fdu.remarks = "do-not-touch"
            fdu.status = "AOG"
            session.add(fdu)
            await session.commit()
            return fdu.id, float(fdu.tach_time_eod), fdu.remarks

    fdu_id, tach, remarks = asyncio.run(_set_and_snapshot())

    response = client.put(
        "/api/v1/aircraft/reorder",
        json={
            "items": [
                {"aircraft_id": b["id"], "display_order": 1},
                {"aircraft_id": a["id"], "display_order": 2},
            ]
        },
    )
    assert response.status_code == 200, response.text

    async def _assert_unchanged() -> None:
        async with TestSessionLocal() as session:
            fdu = (
                await session.execute(
                    select(FleetDailyUpdate).where(FleetDailyUpdate.id == fdu_id)
                )
            ).scalar_one()
            assert float(fdu.tach_time_eod) == tach
            assert fdu.remarks == remarks
            status_val = fdu.status.value if hasattr(fdu.status, "value") else fdu.status
            assert status_val == "AOG"

    asyncio.run(_assert_unchanged())
