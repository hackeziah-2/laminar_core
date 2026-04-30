"""Unit tests for Aircraft Technical Log endpoints."""

import asyncio

from fastapi.testclient import TestClient

from app.api.deps import get_current_active_account
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
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


def test_manage_paged_applies_atl_rbac_filter(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Maintenance Manager should not see PENDING ATL rows on /manage/paged."""
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json={**test_aircraft_technical_log_data, "sequence_no": "ATL-002"},
    )
    assert create_response.status_code == 201
    allowed_log_id = create_response.json()["id"]

    async def seed_pending_row() -> int:
        async with TestSessionLocal() as session:
            pending_row = AircraftTechnicalLog(
                aircraft_fk=test_aircraft_technical_log_data["aircraft_fk"],
                sequence_no="002",
                work_status=WorkStatus.PENDING,
            )
            session.add(pending_row)
            await session.commit()
            await session.refresh(pending_row)
            return pending_row.id

    pending_log_id = asyncio.run(seed_pending_row())

    manage_response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/manage/paged?limit=10&page=1"
    )
    assert manage_response.status_code == 200
    manage_ids = {item["id"] for item in manage_response.json()["items"]}
    assert allowed_log_id in manage_ids
    assert pending_log_id not in manage_ids

    pending_response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/manage/paged?work_status=PENDING&limit=10&page=1"
    )
    assert pending_response.status_code == 200
    assert pending_response.json()["items"] == []
    assert pending_response.json()["total"] == 0


def test_paged_does_not_apply_atl_rbac_filter(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """The general /paged endpoint should remain unfiltered by ATL RBAC."""
    async def seed_pending_row() -> int:
        async with TestSessionLocal() as session:
            pending_row = AircraftTechnicalLog(
                aircraft_fk=test_aircraft_technical_log_data["aircraft_fk"],
                sequence_no="003",
                work_status=WorkStatus.PENDING,
            )
            session.add(pending_row)
            await session.commit()
            await session.refresh(pending_row)
            return pending_row.id

    pending_log_id = asyncio.run(seed_pending_row())

    paged_response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?limit=10&page=1"
    )
    assert paged_response.status_code == 200
    paged_ids = {item["id"] for item in paged_response.json()["items"]}
    assert pending_log_id in paged_ids


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


def test_create_aircraft_technical_log_uses_previous_sequence_for_meter_starts(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Create should default hobbs/tach starts from the previous ATL in sequence order."""
    first_payload = {
        **test_aircraft_technical_log_data,
        "sequence_no": "ATL-001",
        "hobbs_meter_start": 10.0,
        "hobbs_meter_end": 11.5,
        "tachometer_start": 20.0,
        "tachometer_end": 21.25,
    }
    create_first = client_with_atl_auth.post("/api/v1/aircraft-technical-log/", json=first_payload)
    assert create_first.status_code == 201, create_first.text

    second_payload = {
        **test_aircraft_technical_log_data,
        "sequence_no": "ATL-002",
        "hobbs_meter_start": None,
        "hobbs_meter_end": 13.0,
        "tachometer_start": None,
        "tachometer_end": 23.0,
    }
    create_second = client_with_atl_auth.post("/api/v1/aircraft-technical-log/", json=second_payload)
    assert create_second.status_code == 201, create_second.text
    body = create_second.json()
    assert body["hobbs_meter_start"] == 11.5
    assert body["tachometer_start"] == 21.25


def test_update_aircraft_technical_log_allows_meter_start_changes(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Update should allow correcting hobbs/tach start values."""
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    response = client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"hobbs_meter_start": 123.4, "tachometer_start": 234.5},
    )
    assert response.status_code == 200
    assert response.json()["hobbs_meter_start"] == 123.4
    assert response.json()["tachometer_start"] == 234.5


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


def test_quality_manager_can_update_pending_to_completed(client: TestClient):
    """Quality Manager may change ATL work_status from PENDING to COMPLETED."""
    async def seed_role() -> int:
        async with TestSessionLocal() as session:
            role = Role(name="Quality Manager", description="workflow")
            session.add(role)
            await session.commit()
            await session.refresh(role)
            return role.id

    qm_role_id = asyncio.run(seed_role())

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8803
        acc.status = True
        acc.role_id = qm_role_id
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-QM-001",
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
        "work_status": "PENDING",
        "component_parts": [],
    }

    create_response = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]
    assert create_response.json()["work_status"] == WorkStatus.PENDING.value

    update_response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "COMPLETED"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["work_status"] == WorkStatus.COMPLETED.value


def test_quality_manager_can_update_pending_to_rejected_quality(client: TestClient):
    """Quality Manager may change ATL work_status from PENDING to REJECTED_QUALITY."""

    async def seed_role() -> int:
        async with TestSessionLocal() as session:
            role = Role(name="Quality Manager", description="workflow")
            session.add(role)
            await session.commit()
            await session.refresh(role)
            return role.id

    qm_role_id = asyncio.run(seed_role())

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8805
        acc.status = True
        acc.role_id = qm_role_id
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-QM-003",
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
        "work_status": "PENDING",
        "component_parts": [],
    }

    create_response = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "REJECTED_QUALITY"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["work_status"] == WorkStatus.REJECTED_QUALITY.value


def test_quality_manager_cannot_update_for_review_to_completed(client: TestClient):
    """Quality Manager may not skip directly from FOR_REVIEW to COMPLETED."""
    async def seed_role() -> int:
        async with TestSessionLocal() as session:
            role = Role(name="Quality Manager", description="workflow")
            session.add(role)
            await session.commit()
            await session.refresh(role)
            return role.id

    qm_role_id = asyncio.run(seed_role())

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8804
        acc.status = True
        acc.role_id = qm_role_id
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-QM-002",
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
        "work_status": "FOR_REVIEW",
        "component_parts": [],
    }

    create_response = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "COMPLETED"},
    )
    assert update_response.status_code == 403
    assert "cannot change work_status" in update_response.json()["detail"]
