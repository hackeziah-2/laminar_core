"""Unit tests for Aircraft Technical Log endpoints."""
import asyncio

from fastapi.testclient import TestClient

from app.api.deps import get_current_active_account
from app.main import app
from app.models.role import Role
from tests.conftest import TestSessionLocal


def test_atl_paged_requires_authentication(client: TestClient):
    """GET /paged requires a valid session (JWT) or dependency override."""
    response = client.get("/api/v1/aircraft-technical-log/paged?limit=10&page=1")
    assert response.status_code == 401


def test_list_aircraft_technical_logs_empty(client_with_atl_auth: TestClient):
    """Test listing ATL logs when database is empty."""
    response = client_with_atl_auth.get("/api/v1/aircraft-technical-log/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_aircraft_technical_log(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test creating a new aircraft technical log."""
    response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )
    assert response.status_code == 201
    data = response.json()
    # Sequence number stored as number only (e.g. "001"); input "ATL-001" or "001" both stored as "001"
    assert data["sequence_no"] == "001"
    assert data["id"] is not None


def test_get_aircraft_technical_log_not_found(client: TestClient):
    """Test getting a non-existent ATL log."""
    response = client.get("/api/v1/aircraft-technical-log/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_aircraft_technical_logs_with_search(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
    test_aircraft_data: dict,
):
    """Test listing ATL logs with search filter."""
    import json

    # Paged search joins aircraft; need a real aircraft row for the log's FK.
    ar = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert ar.status_code == 200, ar.text
    aircraft_id = ar.json()["id"]
    payload = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_id}
    cr = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=payload,
    )
    assert cr.status_code == 201

    # Search for it (stored as 001; search accepts 001 or ATL-001)
    response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?search=001&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_aircraft_technical_logs_filter_work_status(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Paged list filters by work_status (e.g. APPROVED)."""
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    approved = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&limit=10&page=1"
    )
    assert approved.status_code == 200
    approved_ids = {item["id"] for item in approved.json()["items"]}
    assert log_id not in approved_ids

    client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "APPROVED"},
    )

    approved2 = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&limit=10&page=1"
    )
    assert approved2.status_code == 200
    approved_ids2 = {item["id"] for item in approved2.json()["items"]}
    assert log_id in approved_ids2


def test_update_aircraft_technical_log(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test updating an aircraft technical log."""
    # Create ATL log
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    # Update it
    update_data = {"remarks": "Updated remarks for testing"}
    response = client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json=update_data
    )
    assert response.status_code == 200
    assert response.json()["remarks"] == "Updated remarks for testing"


def test_delete_aircraft_technical_log(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test soft deleting an ATL log."""
    # Create ATL log
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    # Delete it
    response = client_with_atl_auth.delete(f"/api/v1/aircraft-technical-log/{log_id}")
    assert response.status_code == 204


def test_atl_paged_rbac_maintenance_planner_visibility(client: TestClient):
    """Maintenance Planner must not see FOR_REVIEW rows; may see same row after APPROVED."""
    async def seed_roles():
        async with TestSessionLocal() as session:
            mm = Role(name="Maintenance Manager", description="rbac")
            pl = Role(name="Maintenance Planner", description="rbac")
            session.add_all([mm, pl])
            await session.commit()
            await session.refresh(mm)
            await session.refresh(pl)
            return mm.id, pl.id

    mm_rid, pl_rid = asyncio.run(seed_roles())
    acting_role = {"rid": mm_rid}

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8801
        acc.status = True
        acc.role_id = acting_role["rid"]
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-RBAC-PLAN",
        "nature_of_flight": "TR",
        "origin_station": "ORG",
        "origin_date": "2025-01-17",
        "origin_time": "10:00:00",
        "destination_station": "DST",
        "destination_date": "2025-01-17",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 1.0,
        "hobbs_meter_end": 2.0,
        "hobbs_meter_total": 1.0,
        "tachometer_start": 1.0,
        "tachometer_end": 2.0,
        "tachometer_total": 1.0,
        "component_parts": [],
    }
    cr = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert cr.status_code == 201
    log_id = cr.json()["id"]

    acting_role["rid"] = pl_rid
    p1 = client.get("/api/v1/aircraft-technical-log/paged?limit=50&page=1")
    assert p1.status_code == 200
    assert log_id not in {i["id"] for i in p1.json()["items"]}

    acting_role["rid"] = mm_rid
    up = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "APPROVED"},
    )
    assert up.status_code == 200

    acting_role["rid"] = pl_rid
    p2 = client.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&limit=50&page=1"
    )
    assert p2.status_code == 200
    assert log_id in {i["id"] for i in p2.json()["items"]}


def test_atl_paged_admin_sees_all_work_statuses(client: TestClient):
    """Admin lists ATL rows regardless of work_status (e.g. FOR_REVIEW)."""
    async def seed_roles():
        async with TestSessionLocal() as session:
            adm = Role(name="Admin", description="rbac")
            mm = Role(name="Maintenance Manager", description="rbac")
            session.add_all([adm, mm])
            await session.commit()
            await session.refresh(adm)
            await session.refresh(mm)
            return adm.id, mm.id

    adm_rid, mm_rid = asyncio.run(seed_roles())
    acting_role = {"rid": mm_rid}

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8802
        acc.status = True
        acc.role_id = acting_role["rid"]
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-RBAC-ADM",
        "nature_of_flight": "TR",
        "origin_station": "ORG",
        "origin_date": "2025-01-17",
        "origin_time": "10:00:00",
        "destination_station": "DST",
        "destination_date": "2025-01-17",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 1.0,
        "hobbs_meter_end": 2.0,
        "hobbs_meter_total": 1.0,
        "tachometer_start": 1.0,
        "tachometer_end": 2.0,
        "tachometer_total": 1.0,
        "component_parts": [],
    }
    cr = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert cr.status_code == 201
    log_id = cr.json()["id"]
    assert cr.json().get("work_status") in (None, "FOR_REVIEW")

    acting_role["rid"] = adm_rid
    paged = client.get("/api/v1/aircraft-technical-log/paged?limit=50&page=1")
    assert paged.status_code == 200
    assert log_id in {i["id"] for i in paged.json()["items"]}
