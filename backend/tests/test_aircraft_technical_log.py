"""Unit tests for Aircraft Technical Log endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_list_aircraft_technical_logs_empty(client: TestClient):
    """Test listing ATL logs when database is empty."""
    response = client.get("/api/v1/aircraft-technical-log/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_aircraft_technical_log(
    client: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test creating a new aircraft technical log."""
    response = client.post(
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
    client: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test listing ATL logs with search filter."""
    # Create ATL log
    client.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )

    # Search for it (stored as 001; search accepts 001 or ATL-001)
    response = client.get(
        "/api/v1/aircraft-technical-log/paged?search=001&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_aircraft_technical_logs_filter_work_status(
    client: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Paged list filters by work_status (e.g. APPROVED)."""
    create_response = client.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    approved = client.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&limit=10&page=1"
    )
    assert approved.status_code == 200
    approved_ids = {item["id"] for item in approved.json()["items"]}
    assert log_id not in approved_ids

    client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "APPROVED"},
    )

    approved2 = client.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&limit=10&page=1"
    )
    assert approved2.status_code == 200
    approved_ids2 = {item["id"] for item in approved2.json()["items"]}
    assert log_id in approved_ids2


def test_update_aircraft_technical_log(
    client: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test updating an aircraft technical log."""
    # Create ATL log
    create_response = client.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )
    log_id = create_response.json()["id"]

    # Update it
    update_data = {"remarks": "Updated remarks for testing"}
    response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json=update_data
    )
    assert response.status_code == 200
    assert response.json()["remarks"] == "Updated remarks for testing"


def test_delete_aircraft_technical_log(
    client: TestClient,
    test_aircraft_technical_log_data: dict
):
    """Test soft deleting an ATL log."""
    # Create ATL log
    create_response = client.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data
    )
    log_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/aircraft-technical-log/{log_id}")
    assert response.status_code == 204
