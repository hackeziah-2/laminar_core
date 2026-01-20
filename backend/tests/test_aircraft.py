"""Unit tests for Aircraft endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.repository.aircraft import create_aircraft_with_file, list_aircraft
from app.schemas.aircraft_schema import AircraftCreate


def test_list_aircraft_empty(client: TestClient):
    """Test listing aircraft when database is empty."""
    response = client.get("/api/v1/aircraft/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_aircraft(client: TestClient, test_aircraft_data: dict):
    """Test creating a new aircraft."""
    # Convert to form data format
    import json
    json_data = json.dumps(test_aircraft_data)

    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["registration"] == test_aircraft_data["registration"]
    assert data["id"] is not None


def test_get_aircraft_not_found(client: TestClient):
    """Test getting a non-existent aircraft."""
    response = client.get("/api/v1/aircraft/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_aircraft_duplicate_registration(
    client: TestClient,
    test_aircraft_data: dict
):
    """Test creating aircraft with duplicate registration."""
    import json
    json_data = json.dumps(test_aircraft_data)

    # Create first aircraft
    response1 = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )
    assert response1.status_code == 200

    # Try to create duplicate
    response2 = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


def test_list_aircraft_with_search(
    client: TestClient,
    test_aircraft_data: dict
):
    """Test listing aircraft with search filter."""
    import json
    json_data = json.dumps(test_aircraft_data)

    # Create aircraft
    client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )

    # Search for it
    response = client.get("/api/v1/aircraft/paged?search=TEST-001&limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["registration"] == "TEST-001" for item in data["items"])


def test_list_aircraft_pagination(client: TestClient):
    """Test aircraft listing pagination."""
    import json

    # Create multiple aircraft
    for i in range(5):
        aircraft_data = {
            "registration": f"TEST-{i:03d}",
            "manufacturer": "Boeing",
            "type": "Commercial",
            "model": "737-800",
            "msn": f"TEST-MSN-{i:03d}",
            "base": "Test Base",
            "ownership": "Test Owner",
            "status": "Active",
        }
        client.post(
            "/api/v1/aircraft/",
            data={"json_data": json.dumps(aircraft_data)},
            files={}
        )

    # Test pagination
    response = client.get("/api/v1/aircraft/paged?limit=2&page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1


def test_delete_aircraft(client: TestClient, test_aircraft_data: dict):
    """Test soft deleting an aircraft."""
    import json
    json_data = json.dumps(test_aircraft_data)

    # Create aircraft
    create_response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )
    aircraft_id = create_response.json()["id"]

    # Delete aircraft
    response = client.delete(f"/api/v1/aircraft/{aircraft_id}")
    assert response.status_code == 204

    # Verify it's soft deleted (should not appear in list)
    list_response = client.get("/api/v1/aircraft/paged?limit=10&page=1")
    assert list_response.status_code == 200
    data = list_response.json()
    assert not any(item["id"] == aircraft_id for item in data["items"])


@pytest.mark.asyncio
async def test_list_aircraft_repository(db_session: AsyncSession):
    """Test list_aircraft repository function."""
    items, total = await list_aircraft(
        session=db_session,
        limit=10,
        offset=0,
        search=None,
        status="all",
        sort=""
    )
    assert isinstance(total, int)
    assert total >= 0
    assert isinstance(items, list)
