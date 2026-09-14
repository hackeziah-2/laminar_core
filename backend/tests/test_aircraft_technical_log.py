"""Unit tests for Aircraft Technical Log endpoints."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.core.atl_derived_times import ATL_AUTO_FIELD_KEYS, apply_computed_auto_fields_to_row
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from app.main import app
from app.models.role import Role
from app.repository.aircraft_technical_log import (
    _clean_atl_update_data,
    _round_tachometer_total_2,
)
from app.schemas.aircraft_technical_log_schema import (
    AircraftTechnicalLogApiRead,
    ATLPagedItemWithAutoApiRead,
)
from tests.conftest import TestSessionLocal


def test_round_tachometer_total_to_two_decimals():
    assert _round_tachometer_total_2(2.567) == Decimal("2.57")
    assert _round_tachometer_total_2("1.234") == Decimal("1.23")
    assert _round_tachometer_total_2(None) is None
    cleaned = _clean_atl_update_data({"tachometer_total": 9.999})
    assert cleaned["tachometer_total"] == Decimal("10.00")


def test_apply_computed_auto_fields_does_not_overwrite_canonical_times():
    entry = SimpleNamespace(
        airframe_run_time=11.0,
        airframe_aftt=22.0,
        engine_run_time=33.0,
        engine_tso=44.0,
        engine_tbo=55.0,
        propeller_run_time=66.0,
        propeller_tso=77.0,
        propeller_tbo=88.0,
        **{k: None for k in ATL_AUTO_FIELD_KEYS},
    )
    auto = {k: 1.234 for k in ATL_AUTO_FIELD_KEYS}
    apply_computed_auto_fields_to_row(entry, auto)
    assert entry.airframe_run_time == 11.0
    assert entry.airframe_aftt == 22.0
    assert entry.engine_run_time == 33.0
    assert entry.engine_tso == 44.0
    assert entry.engine_tbo == 55.0
    assert entry.propeller_run_time == 66.0
    assert entry.propeller_tso == 77.0
    assert entry.propeller_tbo == 88.0
    assert entry.auto_engine_tso == 1.23


def test_atl_api_read_formats_canonical_time_fields_to_one_decimal():
    """GET /paged and GET /{id} schemas round canonical time fields to 1 decimal."""
    payload = {
        "id": 1,
        "aircraft_fk": 1,
        "sequence_no": "001",
        "airframe_aftt": 10490.54,
        "engine_tsn": "5003.84",
        "engine_tso": 323.74,
        "engine_tbo": -1.54,
        "propeller_tsn": 2432.14,
        "propeller_tso": 323.74,
        "propeller_tbo": 1999.34,
    }
    for schema in (AircraftTechnicalLogApiRead, ATLPagedItemWithAutoApiRead):
        formatted = schema.parse_obj(payload).dict()
        assert formatted["airframe_aftt"] == 10490.5
        assert formatted["engine_tsn"] == 5003.8
        assert formatted["engine_tso"] == 323.7
        assert formatted["engine_tbo"] == -1.5
        assert formatted["propeller_tsn"] == 2432.1
        assert formatted["propeller_tso"] == 323.7
        assert formatted["propeller_tbo"] == 1999.3


@pytest.mark.no_auth
def test_atl_paged_requires_authentication(client: TestClient):
    """GET /paged requires a valid session (JWT) or dependency override."""
    response = client.get("/api/v1/aircraft-technical-log/paged?page_size=50&page=1")
    assert response.status_code == 401


@pytest.mark.no_auth
def test_atl_list_root_requires_authentication(client: TestClient):
    """GET /?search= requires a valid session (JWT) or dependency override."""
    response = client.get("/api/v1/aircraft-technical-log/?search=")
    assert response.status_code == 401


def test_list_aircraft_technical_logs_empty(client_with_atl_auth: TestClient):
    """Test listing ATL logs when database is empty."""
    response = client_with_atl_auth.get("/api/v1/aircraft-technical-log/paged?page_size=50&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_list_aircraft_technical_logs_root_empty_search(client_with_atl_auth: TestClient):
    """GET /?search= lists ATLs; blank search is not a filter and must not 405."""
    response = client_with_atl_auth.get("/api/v1/aircraft-technical-log/?search=")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["total"] == 0
    assert data["pages"] == 0
    assert data["items"] == []


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
        "/api/v1/aircraft-technical-log/paged?search=001&page_size=50&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    root_search = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/?search=001&page_size=50&page=1"
    )
    assert root_search.status_code == 200
    assert root_search.json()["total"] >= 1

    blank_search = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/?search="
    )
    assert blank_search.status_code == 200
    assert blank_search.json()["total"] >= 1


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
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&page_size=50&page=1"
    )
    assert approved.status_code == 200
    approved_ids = {item["id"] for item in approved.json()["items"]}
    assert log_id not in approved_ids

    client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"work_status": "APPROVED"},
    )

    approved2 = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?work_status=APPROVED&page_size=50&page=1"
    )
    assert approved2.status_code == 200
    approved_ids2 = {item["id"] for item in approved2.json()["items"]}
    assert log_id in approved_ids2


def test_manage_paged_maintenance_manager_sees_all_work_statuses(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Maintenance Manager sees all ATL rows on /manage/paged, including PENDING."""
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
        "/api/v1/aircraft-technical-log/manage/paged?page_size=50&page=1"
    )
    assert manage_response.status_code == 200
    manage_ids = {item["id"] for item in manage_response.json()["items"]}
    assert allowed_log_id in manage_ids
    assert pending_log_id in manage_ids

    pending_response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/manage/paged?work_status=PENDING&page_size=50&page=1"
    )
    assert pending_response.status_code == 200
    pending_ids = {item["id"] for item in pending_response.json()["items"]}
    assert pending_log_id in pending_ids
    assert pending_response.json()["total"] >= 1


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
        "/api/v1/aircraft-technical-log/paged?page_size=50&page=1"
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


def test_aircraft_technical_log_web_links_crud(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Create/update/get ATL web link fields."""
    create_payload = {
        **test_aircraft_technical_log_data,
        "white_atl_web_link": "https://example.com/atl/white/initial",
        "dfp_web_link": "https://example.com/atl/dfp/initial",
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=create_payload,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    log_id = created["id"]
    assert created["white_atl_web_link"] == create_payload["white_atl_web_link"]
    assert created["dfp_web_link"] == create_payload["dfp_web_link"]

    update_payload = {
        "white_atl_web_link": "https://example.com/atl/white/updated",
        "dfp_web_link": "https://example.com/atl/dfp/updated",
    }
    update_response = client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json=update_payload,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["white_atl_web_link"] == update_payload["white_atl_web_link"]
    assert updated["dfp_web_link"] == update_payload["dfp_web_link"]

    get_response = client_with_atl_auth.get(f"/api/v1/aircraft-technical-log/{log_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["white_atl_web_link"] == update_payload["white_atl_web_link"]
    assert fetched["dfp_web_link"] == update_payload["dfp_web_link"]


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


def test_update_aircraft_technical_log_persists_client_time_fields(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """PUT must save and return client-supplied time fields without server recomputation."""
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    update_payload = {
        "tachometer_start": 6198,
        "tachometer_end": 61981,
        "tachometer_total": 55783.456,
        "airframe_run_time": 1,
        "airframe_aftt": 1,
        "engine_run_time": 1,
        "engine_tsn": "1",
        "engine_tso": 1,
        "engine_tbo": -1,
        "propeller_run_time": 1,
        "propeller_tsn": 1,
        "propeller_tso": 1,
        "propeller_tbo": 1,
    }
    update_response = client_with_atl_auth.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json=update_payload,
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    expected = {**update_payload, "tachometer_total": 55783.46}
    for key, value in expected.items():
        assert body[key] == value, f"{key}: expected {value}, got {body[key]}"

    get_response = client_with_atl_auth.get(f"/api/v1/aircraft-technical-log/{log_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    decimal_fields = {
        "airframe_aftt",
        "engine_tsn",
        "engine_tso",
        "engine_tbo",
        "propeller_tsn",
        "propeller_tso",
        "propeller_tbo",
    }
    for key, value in expected.items():
        if key in decimal_fields:
            assert fetched[key] == round(float(value), 1), (
                f"GET {key}: expected {round(float(value), 1)}, got {fetched[key]}"
            )
        else:
            assert fetched[key] == value, f"GET {key}: expected {value}, got {fetched[key]}"


def test_create_aircraft_technical_log_persists_client_time_fields_and_rounds_tach_total(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """POST must persist client time fields as sent and round tachometer_total to 2 decimals."""
    payload = {
        **test_aircraft_technical_log_data,
        "sequence_no": "ATL-010",
        "tachometer_total": 2.567,
        "airframe_run_time": 2.5,
        "airframe_aftt": 102.5,
        "engine_run_time": 2.5,
        "engine_total_time": 500.0,
        "engine_tsn": "502.50",
        "engine_tso": 12.5,
        "engine_tbo": 987.5,
        "propeller_run_time": 2.5,
        "propeller_total_time": 200.0,
        "propeller_tsn": 202.5,
        "propeller_tso": 22.5,
        "propeller_tbo": 777.5,
    }
    response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=payload,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tachometer_total"] == 2.57
    assert body["airframe_run_time"] == 2.5
    assert body["airframe_aftt"] == 102.5
    assert body["engine_run_time"] == 2.5
    assert body["engine_total_time"] == 500.0
    assert body["engine_tsn"] == "502.50"
    assert body["engine_tso"] == 12.5
    assert body["engine_tbo"] == 987.5
    assert body["propeller_run_time"] == 2.5
    assert body["propeller_total_time"] == 200.0
    assert body["propeller_tsn"] == 202.5
    assert body["propeller_tso"] == 22.5
    assert body["propeller_tbo"] == 777.5


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


def test_latest_filters_by_batch_id_and_sequence_no(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """GET /latest/batch/{batch_id} returns highest numeric sequence_no within aircraft + batch."""
    from app.models.atl_batch import AtlBatch

    aircraft_fk = test_aircraft_technical_log_data["aircraft_fk"]

    async def seed_batches() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            batch_a = AtlBatch(name="Batch A latest test", description="pytest")
            batch_b = AtlBatch(name="Batch B latest test", description="pytest")
            session.add_all([batch_a, batch_b])
            await session.commit()
            await session.refresh(batch_a)
            await session.refresh(batch_b)
            return batch_a.id, batch_b.id

    batch_a_id, batch_b_id = asyncio.run(seed_batches())
    base = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_fk}

    for seq, batch in [("001", batch_a_id), ("003", batch_a_id), ("999", batch_b_id)]:
        response = client_with_atl_auth.post(
            "/api/v1/aircraft-technical-log/",
            json={**base, "sequence_no": f"ATL-{seq}", "atl_batch_fk": batch},
        )
        assert response.status_code == 201, response.text

    latest_a = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest/batch/{batch_a_id}?aircraft_id={aircraft_fk}"
    )
    assert latest_a.status_code == 200
    assert latest_a.json()["sequence_no"] == "003"
    assert latest_a.json()["atl_batch_fk"] == batch_a_id

    latest_b = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest/batch/{batch_b_id}?aircraft_id={aircraft_fk}"
    )
    assert latest_b.status_code == 200
    assert latest_b.json()["sequence_no"] == "999"

    latest_all = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest?aircraft_id={aircraft_fk}"
    )
    assert latest_all.status_code == 200
    assert latest_all.json()["sequence_no"] == "999"

    empty_batch_response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/latest/batch/999999?aircraft_id=1"
    )
    assert empty_batch_response.status_code == 404
    assert empty_batch_response.json()["detail"] == "No ATL record found for the specified batch."


def test_latest_orders_sequence_no_numerically(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """GET /latest picks highest numeric sequence_no, not lexicographic order."""
    aircraft_fk = test_aircraft_technical_log_data["aircraft_fk"]
    base = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_fk}

    for seq in ["0001", "0002", "0010", "0100", "9"]:
        response = client_with_atl_auth.post(
            "/api/v1/aircraft-technical-log/",
            json={**base, "sequence_no": seq},
        )
        assert response.status_code == 201, response.text

    latest = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest?aircraft_id={aircraft_fk}"
    )
    assert latest.status_code == 200
    assert latest.json()["sequence_no"] == "0100"


def test_latest_not_found_returns_specified_detail(
    client_with_atl_auth: TestClient,
):
    """GET /latest returns 404 with spec detail when no ATL exists for the filter."""
    response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/latest?aircraft_id=999999"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No ATL record found."


def test_latest_with_sequence_no_returns_previous_atl(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """GET /latest?sequence_no= returns nearest predecessor (sequence_no DESC, limit 1)."""
    from app.models.atl_batch import AtlBatch

    aircraft_fk = test_aircraft_technical_log_data["aircraft_fk"]

    async def seed_batch() -> int:
        async with TestSessionLocal() as session:
            batch = AtlBatch(name="Batch prev latest test", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(batch)
            return batch.id

    batch_id = asyncio.run(seed_batch())
    base = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_fk, "atl_batch_fk": batch_id}

    for seq in ["1005", "1006"]:
        response = client_with_atl_auth.post(
            "/api/v1/aircraft-technical-log/",
            json={**base, "sequence_no": f"ATL-{seq}"},
        )
        assert response.status_code == 201, response.text

    previous = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest"
        f"?aircraft_fk={aircraft_fk}&batch_id={batch_id}&sequence_no=1006"
    )
    assert previous.status_code == 200
    assert previous.json()["sequence_no"] == "1005"

    previous_atl_prefix = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest"
        f"?aircraft_fk={aircraft_fk}&batch_id={batch_id}&sequence_no=ATL-1006"
    )
    assert previous_atl_prefix.status_code == 200
    assert previous_atl_prefix.json()["sequence_no"] == "1005"

    missing = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest"
        f"?aircraft_fk={aircraft_fk}&batch_id={batch_id}&sequence_no=1005"
    )
    assert missing.status_code == 404

    no_aircraft = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/latest?sequence_no=1006"
    )
    assert no_aircraft.status_code == 422
    assert "aircraft_id is required" in no_aircraft.json()["detail"]


def test_previous_atl_lookup_skips_soft_deleted_predecessor(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Previous ATL lookup must skip soft-deleted rows in the same batch/aircraft stream."""
    from app.models.atl_batch import AtlBatch

    aircraft_fk = test_aircraft_technical_log_data["aircraft_fk"]

    async def seed_batch() -> int:
        async with TestSessionLocal() as session:
            batch = AtlBatch(name="Batch soft-delete prev test", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(batch)
            return batch.id

    batch_id = asyncio.run(seed_batch())
    base = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_fk, "atl_batch_fk": batch_id}

    created_ids = {}
    for seq in ["1004", "1005", "1006"]:
        response = client_with_atl_auth.post(
            "/api/v1/aircraft-technical-log/",
            json={**base, "sequence_no": f"ATL-{seq}"},
        )
        assert response.status_code == 201, response.text
        created_ids[seq] = response.json()["id"]

    delete_response = client_with_atl_auth.delete(
        f"/api/v1/aircraft-technical-log/{created_ids['1005']}"
    )
    assert delete_response.status_code == 204

    previous = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/latest"
        f"?aircraft_fk={aircraft_fk}&batch_id={batch_id}&sequence_no=1006"
    )
    assert previous.status_code == 200
    assert previous.json()["sequence_no"] == "1004"


def test_create_uses_nearest_active_previous_atl_for_meter_starts(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """Create should chain hobbs/tach starts from the nearest non-deleted predecessor."""
    from app.models.atl_batch import AtlBatch

    aircraft_fk = test_aircraft_technical_log_data["aircraft_fk"]

    async def seed_batch() -> int:
        async with TestSessionLocal() as session:
            batch = AtlBatch(name="Batch meter prev test", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(batch)
            return batch.id

    batch_id = asyncio.run(seed_batch())
    base = {**test_aircraft_technical_log_data, "aircraft_fk": aircraft_fk, "atl_batch_fk": batch_id}

    first = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json={
            **base,
            "sequence_no": "ATL-1004",
            "hobbs_meter_start": 10.0,
            "hobbs_meter_end": 11.0,
            "tachometer_start": 20.0,
            "tachometer_end": 21.0,
        },
    )
    assert first.status_code == 201, first.text

    middle = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json={
            **base,
            "sequence_no": "ATL-1005",
            "hobbs_meter_start": 11.0,
            "hobbs_meter_end": 12.0,
            "tachometer_start": 21.0,
            "tachometer_end": 22.0,
        },
    )
    assert middle.status_code == 201, middle.text
    client_with_atl_auth.delete(f"/api/v1/aircraft-technical-log/{middle.json()['id']}")

    last = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json={
            **base,
            "sequence_no": "ATL-1006",
            "hobbs_meter_start": None,
            "hobbs_meter_end": 13.0,
            "tachometer_start": None,
            "tachometer_end": 23.0,
        },
    )
    assert last.status_code == 201, last.text
    body = last.json()
    assert body["hobbs_meter_start"] == 11.0
    assert body["tachometer_start"] == 21.0


@pytest.mark.asyncio
async def test_get_previous_atl_honors_exclude_atl_id(db_session: AsyncSession):
    """exclude_atl_id skips a row that would otherwise be the immediate predecessor."""
    from app.models.aircraft import Aircraft
    from app.repository.aircraft_technical_log import get_previous_atl

    aircraft = Aircraft(
        registration="TEST-PREV-EXCL",
        model="172",
        msn="MSN-PREV-EXCL",
        base="Base",
        ownership="Owner",
        status="Active",
    )
    db_session.add(aircraft)
    await db_session.flush()

    rows = [
        AircraftTechnicalLog(aircraft_fk=aircraft.id, sequence_no="1004"),
        AircraftTechnicalLog(aircraft_fk=aircraft.id, sequence_no="1005"),
    ]
    db_session.add_all(rows)
    await db_session.flush()

    nearest = await get_previous_atl(db_session, aircraft.id, "1006")
    assert nearest is not None
    assert nearest.id == rows[1].id

    skipped = await get_previous_atl(
        db_session,
        aircraft.id,
        "1006",
        exclude_atl_id=rows[1].id,
    )
    assert skipped is not None
    assert skipped.id == rows[0].id


def test_atl_create_writes_audit_log(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """ATL create should persist a CREATE audit log after commit."""
    from app.constants.audit import ATL_MODULE_NAME

    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    audit_response = client_with_atl_auth.get(
        f"/api/v1/audit-logs/?module_name={ATL_MODULE_NAME}&record_id={log_id}"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    create_logs = [item for item in payload["items"] if item["action"] == "CREATE"]
    assert len(create_logs) == 1
    assert create_logs[0]["table_name"] == "aircraft_technical_log"
    assert create_logs[0]["new_data"]["sequence_no"] == "001"


def test_atl_delete_writes_audit_log(
    client_with_atl_auth: TestClient,
    test_aircraft_technical_log_data: dict,
):
    """ATL delete should persist a DELETE audit log after commit."""
    from app.constants.audit import ATL_MODULE_NAME

    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=test_aircraft_technical_log_data,
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    delete_response = client_with_atl_auth.delete(
        f"/api/v1/aircraft-technical-log/{log_id}"
    )
    assert delete_response.status_code == 204

    audit_response = client_with_atl_auth.get(
        f"/api/v1/audit-logs/?module_name={ATL_MODULE_NAME}&record_id={log_id}&action=DELETE"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    delete_log = payload["items"][0]
    assert delete_log["action"] == "DELETE"
    assert delete_log["old_data"] is not None
    assert delete_log["new_data"] is None


def test_atl_paged_returns_uppercase_signer_names(
    client_with_atl_auth: TestClient,
):
    """GET /paged returns rts_signed_by and pilot_accepted_by as uppercase full names."""
    import asyncio

    from app.core.security import get_password_hash
    from app.models.account import AccountInformation
    from tests.conftest import TestSessionLocal

    rts = client_with_atl_auth.post(
        "/api/v1/account-information/",
        json={
            "first_name": "Juan",
            "middle_name": "Santos",
            "last_name": "Dela Cruz",
            "username": "juan_atl_rts",
            "password": "securepassword123",
            "status": True,
        },
    )
    assert rts.status_code == 201
    rts_id = rts.json()["id"]

    async def _seed_row() -> int:
        async with TestSessionLocal() as session:
            pilot = AccountInformation(
                first_name="pedro",
                middle_name=None,
                last_name="reyes",
                username="pedro_atl_pilot_lower",
                password=get_password_hash("securepassword123"),
                status=True,
            )
            session.add(pilot)
            await session.flush()
            row = AircraftTechnicalLog(
                aircraft_fk=1,
                sequence_no="901",
                work_status=WorkStatus.APPROVED,
                rts_signed_by=rts_id,
                pilot_accepted_by=pilot.id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row.id

    log_id = asyncio.run(_seed_row())

    response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/paged?limit=50&page=1&sort=-created_at"
    )
    assert response.status_code == 200
    item = next(i for i in response.json()["items"] if i["id"] == log_id)
    assert item["rts_signed_by"] == "JUAN SANTOS DELA CRUZ"
    assert item["pilot_accepted_by"] == "PEDRO REYES"


def test_atl_manage_paged_returns_uppercase_signer_names(
    client_with_atl_auth: TestClient,
):
    """GET /manage/paged returns rts_signed_by and pilot_accepted_by as uppercase full names."""
    import asyncio

    from tests.conftest import TestSessionLocal

    rts = client_with_atl_auth.post(
        "/api/v1/account-information/",
        json={
            "first_name": "Juan",
            "middle_name": "Santos",
            "last_name": "Dela Cruz",
            "username": "juan_atl_manage_rts",
            "password": "securepassword123",
            "status": True,
        },
    )
    assert rts.status_code == 201
    rts_id = rts.json()["id"]

    pilot = client_with_atl_auth.post(
        "/api/v1/account-information/",
        json={
            "first_name": "Pedro",
            "last_name": "Reyes",
            "username": "pedro_atl_manage_pilot",
            "password": "securepassword123",
            "status": True,
        },
    )
    assert pilot.status_code == 201
    pilot_id = pilot.json()["id"]

    async def _seed_row() -> int:
        async with TestSessionLocal() as session:
            row = AircraftTechnicalLog(
                aircraft_fk=1,
                sequence_no="902",
                work_status=WorkStatus.APPROVED,
                rts_signed_by=rts_id,
                pilot_accepted_by=pilot_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row.id

    log_id = asyncio.run(_seed_row())

    response = client_with_atl_auth.get(
        "/api/v1/aircraft-technical-log/manage/paged?limit=50&page=1&sort=-created_at"
    )
    assert response.status_code == 200
    item = next(i for i in response.json()["items"] if i["id"] == log_id)
    assert item["rts_signed_by"] == "JUAN SANTOS DELA CRUZ"
    assert item["pilot_accepted_by"] == "PEDRO REYES"
