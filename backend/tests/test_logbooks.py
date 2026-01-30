"""Unit tests for Logbook endpoints (Engine, Airframe, Avionics, Propeller)."""
import json
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft, StatusEnum
from app.models.logbooks import (
    EngineLogbook,
    AirframeLogbook,
    AvionicsLogbook,
    PropellerLogbook
)
from app.repository.logbooks import (
    create_engine_logbook,
    get_engine_logbook,
    list_engine_logbooks,
    update_engine_logbook,
    soft_delete_engine_logbook,
    create_airframe_logbook,
    get_airframe_logbook,
    list_airframe_logbooks,
    update_airframe_logbook,
    soft_delete_airframe_logbook,
    create_avionics_logbook,
    get_avionics_logbook,
    list_avionics_logbooks,
    update_avionics_logbook,
    soft_delete_avionics_logbook,
    create_propeller_logbook,
    get_propeller_logbook,
    list_propeller_logbooks,
    update_propeller_logbook,
    soft_delete_propeller_logbook,
)
from app.schemas.logbook_schema import (
    EngineLogbookCreate,
    EngineLogbookUpdate,
    AirframeLogbookCreate,
    AirframeLogbookUpdate,
    AvionicsLogbookCreate,
    AvionicsLogbookUpdate,
    PropellerLogbookCreate,
    PropellerLogbookUpdate,
)


def _post_logbook(client: TestClient, path: str, data: dict):
    """POST logbook as form data (API expects json_data=Form, upload_file=File)."""
    return client.post(path, data={"json_data": json.dumps(data)}, files={})


def _put_logbook(client: TestClient, path: str, data: dict):
    """PUT logbook as form data (API expects json_data=Form, upload_file=File)."""
    return client.put(path, data={"json_data": json.dumps(data)}, files={})


# ========== Engine Logbook Tests ==========
def test_list_engine_logbook_empty(client: TestClient):
    """Test listing engine logbooks when database is empty."""
    response = client.get("/api/v1/logbooks/engine/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_engine_logbook(client: TestClient, aircraft_id: int):
    """Test creating a new engine logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "engine_tsn": 1000.5,
        "sequence_no": "ENG-001",
        "tach_time": 500.0,
        "engine_tso": 200.0,
        "engine_tbo": 1000.0,
        "description": "Engine inspection",
        "signature": "John Doe",
    }
    response = _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)
    assert response.status_code == 201
    data = response.json()
    assert data["sequence_no"] == logbook_data["sequence_no"]
    assert data["engine_tsn"] == logbook_data["engine_tsn"]
    assert data["id"] is not None


def test_get_engine_logbook(client: TestClient, aircraft_id: int):
    """Test getting a single engine logbook by ID."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "ENG-002",
        "description": "Test entry",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.get(f"/api/v1/logbooks/engine/{logbook_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == logbook_id
    assert data["sequence_no"] == logbook_data["sequence_no"]


def test_get_engine_logbook_not_found(client: TestClient):
    """Test getting a non-existent engine logbook."""
    response = client.get("/api/v1/logbooks/engine/999")
    assert response.status_code == 404


def test_update_engine_logbook(client: TestClient, aircraft_id: int):
    """Test updating an engine logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "ENG-003",
        "description": "Original description",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)
    logbook_id = create_response.json()["id"]

    update_data = {
        "description": "Updated description",
        "engine_tsn": 1500.0,
    }
    response = _put_logbook(client, f"/api/v1/logbooks/engine/{logbook_id}", update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == update_data["description"]
    assert data["engine_tsn"] == update_data["engine_tsn"]


def test_delete_engine_logbook(client: TestClient, aircraft_id: int):
    """Test soft deleting an engine logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "ENG-004",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/logbooks/engine/{logbook_id}")
    assert response.status_code == 204

    # Verify it's soft deleted
    get_response = client.get(f"/api/v1/logbooks/engine/{logbook_id}")
    assert get_response.status_code == 404


# ========== Airframe Logbook Tests ==========
def test_list_airframe_logbook_empty(client: TestClient):
    """Test listing airframe logbooks when database is empty."""
    response = client.get("/api/v1/logbooks/airframe/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


def test_create_airframe_logbook(client: TestClient, aircraft_id: int):
    """Test creating a new airframe logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AF-001",
        "tach_time": 500.0,
        "airframe_time": 2000.0,
        "description": "Airframe inspection",
        "signature": "Jane Smith",
    }
    response = _post_logbook(client, "/api/v1/logbooks/airframe", logbook_data)
    assert response.status_code == 201
    data = response.json()
    assert data["sequence_no"] == logbook_data["sequence_no"]
    assert data["airframe_time"] == logbook_data["airframe_time"]


def test_get_airframe_logbook(client: TestClient, aircraft_id: int):
    """Test getting a single airframe logbook by ID."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AF-002",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/airframe", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.get(f"/api/v1/logbooks/airframe/{logbook_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == logbook_id


def test_update_airframe_logbook(client: TestClient, aircraft_id: int):
    """Test updating an airframe logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AF-003",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/airframe", logbook_data)
    logbook_id = create_response.json()["id"]

    update_data = {"description": "Updated airframe description"}
    response = _put_logbook(client, f"/api/v1/logbooks/airframe/{logbook_id}", update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == update_data["description"]


def test_delete_airframe_logbook(client: TestClient, aircraft_id: int):
    """Test soft deleting an airframe logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AF-004",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/airframe", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/logbooks/airframe/{logbook_id}")
    assert response.status_code == 204


# ========== Avionics Logbook Tests ==========
def test_list_avionics_logbook_empty(client: TestClient):
    """Test listing avionics logbooks when database is empty."""
    response = client.get("/api/v1/logbooks/avionics/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


def test_create_avionics_logbook(client: TestClient, aircraft_id: int):
    """Test creating a new avionics logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "airframe_tsn": 2000.0,
        "sequence_no": "AV-001",
        "component": "GPS Unit",
        "part_no": "PN-12345",
        "serial_no": "SN-67890",
        "description": "Avionics maintenance",
        "signature": "Bob Johnson",
    }
    response = _post_logbook(client, "/api/v1/logbooks/avionics", logbook_data)
    assert response.status_code == 201
    data = response.json()
    assert data["sequence_no"] == logbook_data["sequence_no"]
    assert data["component"] == logbook_data["component"]
    assert data["part_no"] == logbook_data["part_no"]


def test_get_avionics_logbook(client: TestClient, aircraft_id: int):
    """Test getting a single avionics logbook by ID."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AV-002",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/avionics", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.get(f"/api/v1/logbooks/avionics/{logbook_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == logbook_id


def test_update_avionics_logbook(client: TestClient, aircraft_id: int):
    """Test updating an avionics logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AV-003",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/avionics", logbook_data)
    logbook_id = create_response.json()["id"]

    update_data = {"component": "Updated Component", "part_no": "PN-99999"}
    response = _put_logbook(client, f"/api/v1/logbooks/avionics/{logbook_id}", update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["component"] == update_data["component"]


def test_delete_avionics_logbook(client: TestClient, aircraft_id: int):
    """Test soft deleting an avionics logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "AV-004",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/avionics", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/logbooks/avionics/{logbook_id}")
    assert response.status_code == 204


# ========== Propeller Logbook Tests ==========
def test_list_propeller_logbook_empty(client: TestClient):
    """Test listing propeller logbooks when database is empty."""
    response = client.get("/api/v1/logbooks/propeller/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


def test_create_propeller_logbook(client: TestClient, aircraft_id: int):
    """Test creating a new propeller logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "propeller_tsn": 1500.0,
        "sequence_no": "PROP-001",
        "tach_time": 600.0,
        "propeller_tso": 300.0,
        "propeller_tbo": 1500.0,
        "description": "Propeller inspection",
        "signature": "Alice Brown",
    }
    response = _post_logbook(client, "/api/v1/logbooks/propeller", logbook_data)
    assert response.status_code == 201
    data = response.json()
    assert data["sequence_no"] == logbook_data["sequence_no"]
    assert data["propeller_tsn"] == logbook_data["propeller_tsn"]


def test_get_propeller_logbook(client: TestClient, aircraft_id: int):
    """Test getting a single propeller logbook by ID."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "PROP-002",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/propeller", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.get(f"/api/v1/logbooks/propeller/{logbook_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == logbook_id


def test_update_propeller_logbook(client: TestClient, aircraft_id: int):
    """Test updating a propeller logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "PROP-003",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/propeller", logbook_data)
    logbook_id = create_response.json()["id"]

    update_data = {"description": "Updated propeller description"}
    response = _put_logbook(client, f"/api/v1/logbooks/propeller/{logbook_id}", update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == update_data["description"]


def test_delete_propeller_logbook(client: TestClient, aircraft_id: int):
    """Test soft deleting a propeller logbook entry."""
    logbook_data = {
        "aircraft_fk": aircraft_id,
        "date": "2026-01-27",
        "sequence_no": "PROP-004",
    }
    create_response = _post_logbook(client, "/api/v1/logbooks/propeller", logbook_data)
    logbook_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/logbooks/propeller/{logbook_id}")
    assert response.status_code == 204


# ========== Repository Tests ==========
async def _create_test_aircraft(session: AsyncSession) -> int:
    """Create a test aircraft and return its id."""
    aircraft = Aircraft(
        registration="REPO-TEST-001",
        manufacturer="Test",
        type="Test",
        model="Test",
        msn="REPO-MSN-001",
        base="Base",
        ownership="Test",
        status=StatusEnum.ACTIVE,
    )
    session.add(aircraft)
    await session.flush()
    return aircraft.id


@pytest.mark.asyncio
async def test_create_engine_logbook_repository(db_session: AsyncSession):
    """Test create_engine_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = EngineLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="ENG-REPO-001",
        engine_tsn=1000.0,
        description="Repository test",
    )
    created = await create_engine_logbook(db_session, logbook_data)
    assert created.id is not None
    assert created.sequence_no == logbook_data.sequence_no


@pytest.mark.asyncio
async def test_get_engine_logbook_repository(db_session: AsyncSession):
    """Test get_engine_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = EngineLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="ENG-REPO-002",
    )
    created = await create_engine_logbook(db_session, logbook_data)

    retrieved = await get_engine_logbook(db_session, created.id)
    assert retrieved is not None
    assert retrieved.id == created.id

    not_found = await get_engine_logbook(db_session, 999)
    assert not_found is None


@pytest.mark.asyncio
async def test_list_engine_logbooks_repository(db_session: AsyncSession):
    """Test list_engine_logbooks repository function."""
    items, total = await list_engine_logbooks(
        session=db_session, limit=10, offset=0, search=None, sort=""
    )
    assert isinstance(total, int)
    assert total >= 0
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_update_engine_logbook_repository(db_session: AsyncSession):
    """Test update_engine_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = EngineLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="ENG-REPO-003",
    )
    created = await create_engine_logbook(db_session, logbook_data)

    update_data = EngineLogbookUpdate(description="Updated description")
    updated = await update_engine_logbook(db_session, created.id, update_data)
    assert updated is not None
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_soft_delete_engine_logbook_repository(db_session: AsyncSession):
    """Test soft_delete_engine_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = EngineLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="ENG-REPO-004",
    )
    created = await create_engine_logbook(db_session, logbook_data)

    deleted = await soft_delete_engine_logbook(db_session, created.id)
    assert deleted is True

    retrieved = await get_engine_logbook(db_session, created.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_create_airframe_logbook_repository(db_session: AsyncSession):
    """Test create_airframe_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = AirframeLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="AF-REPO-001",
    )
    created = await create_airframe_logbook(db_session, logbook_data)
    assert created.id is not None


@pytest.mark.asyncio
async def test_create_avionics_logbook_repository(db_session: AsyncSession):
    """Test create_avionics_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = AvionicsLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="AV-REPO-001",
        component="Test Component",
    )
    created = await create_avionics_logbook(db_session, logbook_data)
    assert created.id is not None
    assert created.component == "Test Component"


@pytest.mark.asyncio
async def test_create_propeller_logbook_repository(db_session: AsyncSession):
    """Test create_propeller_logbook repository function."""
    aircraft_id = await _create_test_aircraft(db_session)
    logbook_data = PropellerLogbookCreate(
        aircraft_fk=aircraft_id,
        date=date(2026, 1, 27),
        sequence_no="PROP-REPO-001",
    )
    created = await create_propeller_logbook(db_session, logbook_data)
    assert created.id is not None


# ========== Search and Pagination Tests ==========
def test_list_engine_logbook_with_search(client: TestClient, aircraft_id: int):
    """Test listing engine logbooks with search filter."""
    # Create multiple entries
    for i in range(3):
        logbook_data = {
            "aircraft_fk": aircraft_id,
            "date": "2026-01-27",
            "sequence_no": f"ENG-SEARCH-{i}",
            "description": f"Test entry {i}",
        }
        _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)

    response = client.get(
        "/api/v1/logbooks/engine/paged?search=SEARCH-1&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_engine_logbook_pagination(client: TestClient, aircraft_id: int):
    """Test engine logbook listing pagination."""
    # Create multiple entries
    for i in range(5):
        logbook_data = {
            "aircraft_fk": aircraft_id,
            "date": "2026-01-27",
            "sequence_no": f"ENG-PAGE-{i}",
        }
        _post_logbook(client, "/api/v1/logbooks/engine", logbook_data)

    response = client.get("/api/v1/logbooks/engine/paged?limit=2&page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["total"] >= 5
