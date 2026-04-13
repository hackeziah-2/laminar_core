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
    # TSN/TSO default to 0 when not provided
    assert data.get("engine_tsn") == 0
    assert data.get("engine_tso") == 0
    assert data.get("propeller_tsn") == 0
    assert data.get("propeller_tso") == 0


def test_create_aircraft_with_tsn_tso(client: TestClient, test_aircraft_data: dict):
    """Test creating aircraft with engine/propeller TSN and TSO."""
    import json
    payload = {**test_aircraft_data, "msn": "TEST-MSN-TSN"}
    payload["engine_tsn"] = 2500.0
    payload["engine_tso"] = 500.0
    payload["propeller_tsn"] = 1200.5
    payload["propeller_tso"] = 300.0
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["engine_tsn"] == 2500.0
    assert data["engine_tso"] == 500.0
    assert data["propeller_tsn"] == 1200.5
    assert data["propeller_tso"] == 300.0


def test_create_aircraft_negative_tsn_rejected(client: TestClient, test_aircraft_data: dict):
    """Test that negative TSN/TSO values are rejected."""
    import json
    payload = {**test_aircraft_data, "msn": "TEST-MSN-NEG"}
    payload["engine_tsn"] = -1.0
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert response.status_code == 422


def test_update_aircraft_tsn_tso(client: TestClient, test_aircraft_data: dict):
    """Test updating only engine_tso (partial update)."""
    import json
    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert create_resp.status_code == 200
    aircraft_id = create_resp.json()["id"]
    update_resp = client.put(
        f"/api/v1/aircraft/{aircraft_id}",
        data={"json_data": json.dumps({"engine_tso": 550.0})},
        files={},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["engine_tso"] == 550.0


def test_create_read_update_aircraft_model_year(client: TestClient, test_aircraft_data: dict):
    """Test CRUD for model_year: create with model_year, read returns it, update it."""
    import json
    payload = {**test_aircraft_data, "msn": "TEST-MSN-YEAR"}
    payload["model_year"] = 2015
    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["model_year"] == 2015
    aircraft_id = create_resp.json()["id"]
    get_resp = client.get(f"/api/v1/aircraft/{aircraft_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["model_year"] == 2015
    update_resp = client.put(
        f"/api/v1/aircraft/{aircraft_id}",
        data={"json_data": json.dumps({"model_year": 2018})},
        files={},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["model_year"] == 2018


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
