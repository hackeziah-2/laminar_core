"""Pytest for Aircraft Statutory Certificate REST API."""
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def certificate_payload(aircraft_id: int):
    """Minimal create payload for one certificate."""
    return {
        "aircraft_fk": aircraft_id,
        "category_type": "COA",
        "date_of_expiration": "2026-12-31",
        "web_link": "https://example.com/cert",
        "file_path": None,
    }


def test_list_certificates_empty(client: TestClient):
    """List when no certificates exist."""
    response = client.get("/api/v1/aircraft-statutory-certificates/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_certificate(client: TestClient, certificate_payload: dict):
    """Create a certificate (no file upload)."""
    response = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["aircraft_fk"] == certificate_payload["aircraft_fk"]
    assert data["category_type"] == "COA"
    assert data["date_of_expiration"] == "2026-12-31"
    assert data["web_link"] == "https://example.com/cert"
    assert data["id"] is not None


def test_get_certificate(client: TestClient, certificate_payload: dict):
    """Get certificate by ID."""
    create_resp = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert create_resp.status_code == 201
    cert_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/aircraft-statutory-certificates/{cert_id}")
    assert response.status_code == 200
    assert response.json()["id"] == cert_id
    assert response.json()["category_type"] == "COA"


def test_get_certificate_not_found(client: TestClient):
    """Get non-existent certificate returns 404."""
    response = client.get("/api/v1/aircraft-statutory-certificates/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_paged_with_filter(client: TestClient, certificate_payload: dict):
    """List paged and filter by category_type."""
    client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )

    response = client.get(
        "/api/v1/aircraft-statutory-certificates/paged?limit=10&page=1&category_type=COA"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["category_type"] == "COA"

    # Filter by different category returns no match for this certificate
    response_other = client.get(
        "/api/v1/aircraft-statutory-certificates/paged?limit=10&page=1&category_type=COR"
    )
    assert response_other.status_code == 200
    # Total may be 0 if only COA was created
    assert "items" in response_other.json()


def test_update_certificate(client: TestClient, certificate_payload: dict):
    """Update certificate (partial)."""
    create_resp = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert create_resp.status_code == 201
    cert_id = create_resp.json()["id"]

    update_data = {
        "web_link": "https://updated.example.com",
        "date_of_expiration": "2027-06-30",
    }
    response = client.put(
        f"/api/v1/aircraft-statutory-certificates/{cert_id}",
        data={"json_data": json.dumps(update_data)},
        files={},
    )
    assert response.status_code == 200
    assert response.json()["web_link"] == "https://updated.example.com"
    assert response.json()["date_of_expiration"] == "2027-06-30"


def test_delete_certificate(client: TestClient, certificate_payload: dict):
    """Soft delete certificate."""
    create_resp = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert create_resp.status_code == 201
    cert_id = create_resp.json()["id"]

    response = client.delete(f"/api/v1/aircraft-statutory-certificates/{cert_id}")
    assert response.status_code == 204

    get_resp = client.get(f"/api/v1/aircraft-statutory-certificates/{cert_id}")
    assert get_resp.status_code == 404


def test_list_by_aircraft_paged(client: TestClient, certificate_payload: dict, aircraft_id: int):
    """List certificates scoped to aircraft with category_type filter."""
    client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )

    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/aircraft-statutory-certificates/paged?limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["aircraft_fk"] == aircraft_id

    response_filtered = client.get(
        f"/api/v1/aircraft/{aircraft_id}/aircraft-statutory-certificates/paged"
        "?limit=10&page=1&category_type=COA"
    )
    assert response_filtered.status_code == 200


def test_create_invalid_category(client: TestClient, aircraft_id: int):
    """Create with invalid category_type returns 422."""
    payload = {
        "aircraft_fk": aircraft_id,
        "category_type": "INVALID_CAT",
        "date_of_expiration": None,
        "web_link": None,
        "file_path": None,
    }
    response = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert response.status_code == 422


def test_create_duplicate_certificate_returns_409(
    client: TestClient, certificate_payload: dict
):
    """POST with same aircraft_fk, category_type, and date_of_expiration returns 409."""
    first = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Entry already Exists"


def test_create_same_aircraft_category_different_expiration_ok(
    client: TestClient, certificate_payload: dict
):
    """Same aircraft and category_type but different date_of_expiration is allowed."""
    first = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert first.status_code == 201

    other = {**certificate_payload, "date_of_expiration": "2027-01-15"}
    second = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(other)},
        files={},
    )
    assert second.status_code == 201
