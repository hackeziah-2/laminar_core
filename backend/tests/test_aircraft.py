"""Unit tests for Aircraft endpoints."""
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.models.aircraft_history import AircraftHistory
from app.repository.aircraft import create_aircraft_with_file, list_aircraft
from app.schemas.aircraft_schema import AircraftCreate
from tests.conftest import TestSessionLocal


@pytest.mark.no_auth
def test_list_aircraft_empty(client: TestClient):
    """Test listing aircraft when database is empty."""
    response = client.get("/api/v1/aircraft/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_list_aircraft_minimal(client: TestClient):
    """Test the minimal aircraft list endpoint returns id and registration only."""
    import json

    payloads = [
        {
            "registration": "TEST-002",
            "model": "737-800",
            "msn": "TEST-MSN-002",
            "base": "Test Base",
            "ownership": "Test Owner",
            "status": "Active",
        },
        {
            "registration": "TEST-001",
            "model": "A320",
            "msn": "TEST-MSN-001",
            "base": "Test Base",
            "ownership": "Test Owner",
            "status": "Active",
        },
    ]

    for payload in payloads:
        response = client.post(
            "/api/v1/aircraft/",
            data={"json_data": json.dumps(payload)},
            files={},
        )
        assert response.status_code == 200

    response = client.get("/api/v1/aircraft/list")
    assert response.status_code == 200
    data = response.json()

    assert data == [
        {"id": 2, "registration": "TEST-001"},
        {"id": 1, "registration": "TEST-002"},
    ]


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
    # TSO defaults to 0; TSN fields are optional (null when omitted)
    assert data.get("engine_tsn") is None
    assert data.get("engine_tso") == 0
    assert data.get("propeller_tsn") is None
    assert data.get("propeller_tso") == 0


def test_create_aircraft_with_tsn_tso(client: TestClient, test_aircraft_data: dict):
    """Test creating aircraft with airframe, engine, and propeller time fields."""
    import json
    payload = {**test_aircraft_data, "msn": "TEST-MSN-TSN"}
    payload["airframe_aftt"] = 3200.25
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
    assert data["airframe_aftt"] == 3200.25
    assert data["engine_tsn"] == 2500.0
    assert data["engine_tso"] == 500.0
    assert data["propeller_tsn"] == 1200.5
    assert data["propeller_tso"] == 300.0


def test_update_aircraft_airframe_aftt(client: TestClient, test_aircraft_data: dict):
    """Test updating airframe_aftt through the main PUT API and logging history."""
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
        data={"json_data": json.dumps({"airframe_aftt": 150.75})},
        files={},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["airframe_aftt"] == 150.75

    history_resp = client.get(f"/api/v1/aircraft/{aircraft_id}/history?limit=10&page=1")
    assert history_resp.status_code == 200
    history_body = history_resp.json()
    history_rows = history_body["items"]
    assert history_body["total"] == 1
    assert len(history_rows) == 1
    assert history_rows[0]["field_name"] == "airframe_aftt"
    assert history_rows[0]["old_value"] is None
    assert history_rows[0]["new_value"] == "150.75"


def test_create_aircraft_negative_tsn_rejected(client: TestClient, test_aircraft_data: dict):
    """Test that negative TSN values are rejected at validation."""
    import json

    from pydantic import ValidationError

    from app.schemas.aircraft_schema import AircraftCreate

    payload = {**test_aircraft_data, "msn": "TEST-MSN-NEG", "engine_tsn": -1.0}
    with pytest.raises(ValidationError):
        AircraftCreate(**payload)


def test_update_aircraft_tsn_tso(client: TestClient, test_aircraft_data: dict):
    """Test updating only engine_tso (partial update) and logging history on the main PUT API."""
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

    history_resp = client.get(f"/api/v1/aircraft/{aircraft_id}/history?limit=10&page=1")
    assert history_resp.status_code == 200
    history_body = history_resp.json()
    history_rows = history_body["items"]
    assert history_body["total"] == 1
    assert history_body["page"] == 1
    assert history_body["pages"] == 1
    assert len(history_rows) == 1
    assert history_rows[0]["field_name"] == "engine_tso"
    assert history_rows[0]["old_value"] == "0.0"
    assert history_rows[0]["new_value"] == "550.0"
    assert history_rows[0]["changed_by_name"]


def test_get_aircraft_history_returns_entries_in_read_api(client: TestClient, test_aircraft_data: dict):
    """Test aircraft history can be read from the aircraft API after tracked updates."""
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
        data={"json_data": json.dumps({"engine_model": "PT6A-114A", "propeller_tso": 120.5})},
        files={},
    )
    assert update_resp.status_code == 200

    history_resp = client.get(f"/api/v1/aircraft/{aircraft_id}/history?limit=10&page=1")
    assert history_resp.status_code == 200, history_resp.text
    body = history_resp.json()
    rows = body["items"]
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["pages"] == 1
    assert len(rows) == 2
    assert {row["field_name"] for row in rows} == {"engine_model", "propeller_tso"}
    assert all(row["action_type"] == "UPDATE" for row in rows)
    assert all(row["changed_by_name"] for row in rows)


def test_get_aircraft_history_supports_pagination(client: TestClient, test_aircraft_data: dict):
    """Test aircraft history endpoint paginates change records."""
    import json

    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert create_resp.status_code == 200
    aircraft_id = create_resp.json()["id"]

    client.put(
        f"/api/v1/aircraft/{aircraft_id}",
        data={"json_data": json.dumps({"engine_model": "PT6A-114A", "propeller_tso": 120.5})},
        files={},
    )

    page_1 = client.get(f"/api/v1/aircraft/{aircraft_id}/history?limit=1&page=1")
    assert page_1.status_code == 200, page_1.text
    body_1 = page_1.json()
    assert body_1["total"] == 2
    assert body_1["page"] == 1
    assert body_1["pages"] == 2
    assert len(body_1["items"]) == 1

    page_2 = client.get(f"/api/v1/aircraft/{aircraft_id}/history?limit=1&page=2")
    assert page_2.status_code == 200, page_2.text
    body_2 = page_2.json()
    assert body_2["total"] == 2
    assert body_2["page"] == 2
    assert body_2["pages"] == 2
    assert len(body_2["items"]) == 1


def test_update_aircraft_with_history_creates_records(client: TestClient, test_aircraft_data: dict):
    """Test update-with-history stores one row per modified field."""
    import json

    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert create_resp.status_code == 200
    aircraft_id = create_resp.json()["id"]

    update_resp = client.post(
        f"/api/v1/aircraft/{aircraft_id}/update-with-history",
        data={"json_data": json.dumps({"engine_model": "PT6A-114A", "propeller_tso": 120.5})},
        files={},
    )
    assert update_resp.status_code == 200, update_resp.text
    body = update_resp.json()
    assert body["aircraft"]["engine_model"] == "PT6A-114A"
    assert body["aircraft"]["propeller_tso"] == 120.5
    assert len(body["history_records"]) == 2
    assert {item["field_name"] for item in body["history_records"]} == {"engine_model", "propeller_tso"}
    assert all(item["action_type"] == "UPDATE" for item in body["history_records"])
    assert all(item["changed_at"] for item in body["history_records"])

    async def fetch_history_rows():
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(AircraftHistory)
                .where(AircraftHistory.aircraft_id == aircraft_id)
                .order_by(AircraftHistory.field_name.asc())
            )
            return result.scalars().all()

    rows = asyncio.run(fetch_history_rows())
    assert len(rows) == 2
    assert rows[0].changed_at is not None
    assert {row.field_name for row in rows} == {"engine_model", "propeller_tso"}


def test_update_aircraft_with_history_skips_unchanged_values(client: TestClient, test_aircraft_data: dict):
    """Test update-with-history does not create rows when nothing changed."""
    import json

    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    aircraft_id = created["id"]

    update_resp = client.post(
        f"/api/v1/aircraft/{aircraft_id}/update-with-history",
        data={"json_data": json.dumps({"registration": created["registration"]})},
        files={},
    )
    assert update_resp.status_code == 200, update_resp.text
    body = update_resp.json()
    assert body["history_records"] == []
    assert body["aircraft"]["registration"] == created["registration"]

    async def count_history_rows():
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(AircraftHistory).where(AircraftHistory.aircraft_id == aircraft_id)
            )
            return len(result.scalars().all())

    assert asyncio.run(count_history_rows()) == 0


def test_update_aircraft_with_history_handles_null_field_transitions(
    client: TestClient, test_aircraft_data: dict
):
    """Test null to value updates are recorded safely."""
    import json

    create_resp = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert create_resp.status_code == 200
    aircraft_id = create_resp.json()["id"]

    update_resp = client.post(
        f"/api/v1/aircraft/{aircraft_id}/update-with-history",
        data={"json_data": json.dumps({"engine_serial_number": "ENG-001"})},
        files={},
    )
    assert update_resp.status_code == 200, update_resp.text
    row = update_resp.json()["history_records"][0]
    assert row["field_name"] == "engine_serial_number"
    assert row["old_value"] is None
    assert row["new_value"] == "ENG-001"


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


@pytest.mark.no_auth
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
