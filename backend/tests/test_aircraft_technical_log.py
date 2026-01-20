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
    assert data["sequence_no"] == test_aircraft_technical_log_data["sequence_no"]
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

    # Search for it
    response = client.get(
        "/api/v1/aircraft-technical-log/paged?search=ATL-001&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


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
