"""API tests for TCC / CPCP persistent display_order reorder."""
from __future__ import annotations

import asyncio
from typing import List, Tuple
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.aircraft import Aircraft
from app.models.cpcp_monitoring import CPCPMonitoring
from app.models.tcc_maintenance import TCCMaintenance
from app.repository.cpcp_monitoring import list_cpcp_monitorings
from app.repository.tcc_maintenance import list_tcc_maintenances
from app.schemas.cpcp_monitoring_schema import CPCPMonitoringRead
from app.services.tcc_computation import COMPUTED_TCC_COLUMN_KEYS
from tests.conftest import TestSessionLocal
from tests.factories.import_files import cpcp_csv_bytes, tcc_csv_bytes


async def _cpcp_read_from_orm(session, obj):
    """Avoid Postgres-only ATL metric queries in SQLite tests."""
    return CPCPMonitoringRead.from_orm(obj)


async def _seed_aircraft(registration: str, msn: str) -> int:
    async with TestSessionLocal() as session:
        ac = Aircraft(
            registration=registration,
            model="172",
            msn=msn,
            base="Base",
            ownership="Owner",
            status="Active",
        )
        session.add(ac)
        await session.commit()
        await session.refresh(ac)
        return ac.id


async def _seed_tcc_rows(
    aircraft_id: int,
    descriptions: List[str],
) -> List[Tuple[int, str, int]]:
    """Create TCC rows with sequential display_order. Returns (id, description, order)."""
    async with TestSessionLocal() as session:
        rows = []
        for index, description in enumerate(descriptions, start=1):
            row = TCCMaintenance(
                aircraft_fk=aircraft_id,
                part_number=f"PN-{description}",
                description=description,
                category="Airframe",
                display_order=index,
            )
            session.add(row)
            rows.append(row)
        await session.commit()
        for row in rows:
            await session.refresh(row)
        return [(row.id, row.description, row.display_order) for row in rows]


async def _seed_cpcp_rows(
    aircraft_id: int,
    descriptions: List[str],
) -> List[Tuple[int, str, int]]:
    """Create CPCP rows with sequential display_order. Returns (id, description, order)."""
    async with TestSessionLocal() as session:
        rows = []
        for index, description in enumerate(descriptions, start=1):
            row = CPCPMonitoring(
                aircraft_id=aircraft_id,
                inspection_operation=f"Op {description}",
                description=description,
                display_order=index,
            )
            session.add(row)
            rows.append(row)
        await session.commit()
        for row in rows:
            await session.refresh(row)
        return [(row.id, row.description, row.display_order) for row in rows]


async def _tcc_list_order(aircraft_id: int) -> Tuple[List[str], List[int]]:
    async with TestSessionLocal() as session:
        items, _ = await list_tcc_maintenances(
            session, limit=50, offset=0, aircraft_fk=aircraft_id
        )
        return [i.description for i in items], [i.display_order for i in items]


async def _cpcp_list_order(aircraft_id: int) -> Tuple[List[str], List[int]]:
    async with TestSessionLocal() as session:
        items, _ = await list_cpcp_monitorings(
            session, limit=50, offset=0, aircraft_id=aircraft_id
        )
        return [i.description for i in items], [i.display_order for i in items]


def test_tcc_reorder_success_and_persists(client: TestClient):
    """Successful TCC reorder; arrangement persists on list retrieve."""
    aircraft_id = asyncio.run(_seed_aircraft("TCC-REORDER-AC", "TCC-REORDER-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B", "C"]))
    id_a, id_b, id_c = seeded[0][0], seeded[1][0], seeded[2][0]

    payload = {
        "items": [
            {"id": id_c, "display_order": 1},
            {"id": id_a, "display_order": 2},
            {"id": id_b, "display_order": 3},
        ]
    }
    response = client.put("/api/v1/maintenance-tcc/reorder", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["description"] for item in body["items"]] == ["C", "A", "B"]
    assert [item["display_order"] for item in body["items"]] == [1, 2, 3]

    descriptions, orders = asyncio.run(_tcc_list_order(aircraft_id))
    assert descriptions == ["C", "A", "B"]
    assert orders == [1, 2, 3]


def test_cpcp_reorder_success_and_persists(client: TestClient):
    """Successful CPCP reorder; arrangement persists on list retrieve."""
    aircraft_id = asyncio.run(_seed_aircraft("CPCP-REORDER-AC", "CPCP-REORDER-MSN"))
    seeded = asyncio.run(_seed_cpcp_rows(aircraft_id, ["A", "B", "C"]))
    id_a, id_b, id_c = seeded[0][0], seeded[1][0], seeded[2][0]

    response = client.put(
        "/api/v1/maintenance-cpcp/reorder",
        json={
            "items": [
                {"id": id_c, "display_order": 1},
                {"id": id_a, "display_order": 2},
                {"id": id_b, "display_order": 3},
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["description"] for item in body["items"]] == ["C", "A", "B"]
    assert [item["display_order"] for item in body["items"]] == [1, 2, 3]

    descriptions, orders = asyncio.run(_cpcp_list_order(aircraft_id))
    assert descriptions == ["C", "A", "B"]
    assert orders == [1, 2, 3]


def test_tcc_reorder_rejects_duplicate_ids(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("TCC-DUP-ID-AC", "TCC-DUP-ID-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B"]))
    id_a = seeded[0][0]

    response = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": id_a, "display_order": 1},
                {"id": id_a, "display_order": 2},
            ]
        },
    )
    assert response.status_code == 400
    assert "Duplicate record IDs" in response.json()["detail"]


def test_tcc_reorder_rejects_missing_ids(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("TCC-MISS-AC", "TCC-MISS-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A"]))
    id_a = seeded[0][0]

    response = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": id_a, "display_order": 1},
                {"id": 999999, "display_order": 2},
            ]
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_tcc_reorder_rejects_invalid_and_duplicate_display_order(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("TCC-BAD-ORD-AC", "TCC-BAD-ORD-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B"]))
    id_a, id_b = seeded[0][0], seeded[1][0]

    dup_order = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": id_a, "display_order": 1},
                {"id": id_b, "display_order": 1},
            ]
        },
    )
    assert dup_order.status_code == 400
    assert "Duplicate display_order" in dup_order.json()["detail"]

    non_sequential = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": id_a, "display_order": 1},
                {"id": id_b, "display_order": 3},
            ]
        },
    )
    assert non_sequential.status_code == 400
    assert "sequential" in non_sequential.json()["detail"].lower()


def test_tcc_reorder_rolls_back_when_one_item_invalid(client: TestClient):
    """Invalid item rejects entire batch; existing display_order values unchanged."""
    aircraft_id = asyncio.run(_seed_aircraft("TCC-RB-AC", "TCC-RB-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B", "C"]))
    id_a, id_b, id_c = seeded[0][0], seeded[1][0], seeded[2][0]

    response = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": id_c, "display_order": 1},
                {"id": id_a, "display_order": 2},
                {"id": 999999, "display_order": 3},
            ]
        },
    )
    assert response.status_code == 404

    descriptions, orders = asyncio.run(_tcc_list_order(aircraft_id))
    assert descriptions == ["A", "B", "C"]
    assert orders == [1, 2, 3]


def test_tcc_create_appends_last_display_order(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("TCC-APPEND-AC", "TCC-APPEND-MSN"))
    asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B"]))

    with patch(
        "app.repository.tcc_maintenance.build_computed_tcc_field_values",
        new_callable=AsyncMock,
        return_value={k: None for k in COMPUTED_TCC_COLUMN_KEYS},
    ):
        response = client.post(
            "/api/v1/tcc-maintenance/",
            json={
                "aircraft_fk": aircraft_id,
                "part_number": "PN-NEW",
                "description": "NEW",
                "category": "Airframe",
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["display_order"] == 3

    descriptions, orders = asyncio.run(_tcc_list_order(aircraft_id))
    assert descriptions == ["A", "B", "NEW"]
    assert orders == [1, 2, 3]


def test_cpcp_create_appends_last_display_order(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("CPCP-APPEND-AC", "CPCP-APPEND-MSN"))
    asyncio.run(_seed_cpcp_rows(aircraft_id, ["A", "B"]))

    with patch(
        "app.repository.cpcp_monitoring.to_cpcp_monitoring_read",
        new=_cpcp_read_from_orm,
    ):
        response = client.post(
            "/api/v1/cpcp-monitoring/",
            json={
                "aircraft_id": aircraft_id,
                "inspection_operation": "Op NEW",
                "description": "NEW",
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["display_order"] == 3

    descriptions, orders = asyncio.run(_cpcp_list_order(aircraft_id))
    assert descriptions == ["A", "B", "NEW"]
    assert orders == [1, 2, 3]


def test_tcc_delete_normalizes_remaining_display_order(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("TCC-DEL-AC", "TCC-DEL-MSN"))
    seeded = asyncio.run(_seed_tcc_rows(aircraft_id, ["A", "B", "C"]))
    id_b = seeded[1][0]

    deleted = client.delete(f"/api/v1/tcc-maintenance/{id_b}")
    assert deleted.status_code == 204, deleted.text

    descriptions, orders = asyncio.run(_tcc_list_order(aircraft_id))
    assert descriptions == ["A", "C"]
    assert orders == [1, 2]


def test_cpcp_delete_normalizes_remaining_display_order(client: TestClient):
    aircraft_id = asyncio.run(_seed_aircraft("CPCP-DEL-AC", "CPCP-DEL-MSN"))
    seeded = asyncio.run(_seed_cpcp_rows(aircraft_id, ["A", "B", "C"]))
    id_b = seeded[1][0]

    deleted = client.delete(f"/api/v1/cpcp-monitoring/{id_b}")
    assert deleted.status_code == 204, deleted.text

    descriptions, orders = asyncio.run(_cpcp_list_order(aircraft_id))
    assert descriptions == ["A", "C"]
    assert orders == [1, 2]


@pytest.mark.no_auth
def test_reorder_unauthorized(client: TestClient):
    response_tcc = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={"items": [{"id": 1, "display_order": 1}]},
    )
    assert response_tcc.status_code == 401

    response_cpcp = client.put(
        "/api/v1/maintenance-cpcp/reorder",
        json={"items": [{"id": 1, "display_order": 1}]},
    )
    assert response_cpcp.status_code == 401


def test_tcc_ids_rejected_on_cpcp_reorder_and_vice_versa(client: TestClient):
    """Wrong-module endpoints only look up their own tables (missing IDs → 404)."""
    tcc_aircraft = asyncio.run(_seed_aircraft("XMOD-TCC-AC", "XMOD-TCC-MSN"))
    cpcp_aircraft = asyncio.run(_seed_aircraft("XMOD-CPCP-AC", "XMOD-CPCP-MSN"))
    tcc_rows = asyncio.run(_seed_tcc_rows(tcc_aircraft, ["T1", "T2"]))
    cpcp_rows = asyncio.run(_seed_cpcp_rows(cpcp_aircraft, ["C1", "C2"]))

    # Use TCC primary keys against CPCP table only — they must not exist there.
    # (SQLite autoincrement is per-table, so mirror IDs can collide; offset avoids that.)
    tcc_only_ids = [row[0] + 10_000 for row in tcc_rows]
    cpcp_resp = client.put(
        "/api/v1/maintenance-cpcp/reorder",
        json={
            "items": [
                {"id": tcc_only_ids[0], "display_order": 1},
                {"id": tcc_only_ids[1], "display_order": 2},
            ]
        },
    )
    assert cpcp_resp.status_code == 404

    cpcp_only_ids = [row[0] + 10_000 for row in cpcp_rows]
    tcc_resp = client.put(
        "/api/v1/maintenance-tcc/reorder",
        json={
            "items": [
                {"id": cpcp_only_ids[0], "display_order": 1},
                {"id": cpcp_only_ids[1], "display_order": 2},
            ]
        },
    )
    assert tcc_resp.status_code == 404

    # Real TCC ids must not mutate when sent to the CPCP endpoint if they happen
    # to collide with CPCP ids — assert each endpoint only updates its own model.
    async def _assert_modules_isolated() -> None:
        async with TestSessionLocal() as session:
            tcc = (
                await session.execute(
                    select(TCCMaintenance).where(
                        TCCMaintenance.aircraft_fk == tcc_aircraft
                    )
                )
            ).scalars().all()
            cpcp = (
                await session.execute(
                    select(CPCPMonitoring).where(
                        CPCPMonitoring.aircraft_id == cpcp_aircraft
                    )
                )
            ).scalars().all()
            assert sorted(r.display_order for r in tcc) == [1, 2]
            assert sorted(r.display_order for r in cpcp) == [1, 2]

    asyncio.run(_assert_modules_isolated())


def test_excel_import_order_preserved_tcc_and_cpcp(
    client_with_maintenance_import_auth: TestClient,
):
    """Excel import assigns display_order from row position (covered for both modules)."""
    tcc_aircraft = asyncio.run(_seed_aircraft("IMP-TCC-ORD", "IMP-TCC-ORD-MSN"))
    cpcp_aircraft = asyncio.run(_seed_aircraft("IMP-CPCP-ORD", "IMP-CPCP-ORD-MSN"))

    tcc_rows = [
        {"Category": "AIRFRAME", "Description": "A", "Part Number": "PN-A"},
        {"Category": "AIRFRAME", "Description": "C", "Part Number": "PN-C"},
        {"Category": "AIRFRAME", "Description": "B", "Part Number": "PN-B"},
    ]
    with patch(
        "app.services.excel_import.hooks.maintenance_tcc.build_computed_tcc_field_values",
        new_callable=AsyncMock,
        return_value={k: None for k in COMPUTED_TCC_COLUMN_KEYS},
    ):
        tcc_resp = client_with_maintenance_import_auth.post(
            "/api/v1/excel-data/maintenance-tcc/import",
            data={"aircraft_id": str(tcc_aircraft)},
            files={"file": ("tcc.csv", tcc_csv_bytes(tcc_rows), "text/csv")},
        )
    assert tcc_resp.status_code == 200, tcc_resp.text
    assert tcc_resp.json()["status"] == "success"

    cpcp_rows = [
        {"Inspection Operation": "Op A", "Description": "A"},
        {"Inspection Operation": "Op C", "Description": "C"},
        {"Inspection Operation": "Op B", "Description": "B"},
    ]
    cpcp_resp = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-cpcp/import",
        data={"aircraft_id": str(cpcp_aircraft)},
        files={"file": ("cpcp.csv", cpcp_csv_bytes(cpcp_rows), "text/csv")},
    )
    assert cpcp_resp.status_code == 200, cpcp_resp.text
    assert cpcp_resp.json()["status"] == "success"

    tcc_desc, tcc_ord = asyncio.run(_tcc_list_order(tcc_aircraft))
    assert tcc_desc == ["A", "C", "B"]
    assert tcc_ord == [1, 2, 3]

    cpcp_desc, cpcp_ord = asyncio.run(_cpcp_list_order(cpcp_aircraft))
    assert cpcp_desc == ["A", "C", "B"]
    assert cpcp_ord == [1, 2, 3]
