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


def test_create_duplicate_updates_existing_and_appends_history(
    client: TestClient, certificate_payload: dict, aircraft_id: int
):
    """POST with same aircraft_fk and category_type updates the row and records prior state in history."""
    first = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert first.status_code == 201
    cert_id = first.json()["id"]

    hold_resp = client.put(
        f"/api/v1/aircraft-statutory-certificates/{cert_id}",
        data={"json_data": json.dumps({"is_withhold": True})},
        files={},
    )
    assert hold_resp.status_code == 200
    assert hold_resp.json()["is_withhold"] is True

    updated_payload = {
        **certificate_payload,
        "date_of_expiration": "2028-01-01",
        "web_link": "https://example.com/renewed",
    }
    second = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(updated_payload)},
        files={},
    )
    assert second.status_code == 201
    body = second.json()
    assert body["id"] == cert_id
    assert body["date_of_expiration"] == "2028-01-01"
    assert body["web_link"] == "https://example.com/renewed"
    assert body["is_withhold"] is False

    hist = client.get(
        f"/api/v1/aircraft-statutory-certificates-history/paged?limit=10&page=1"
        f"&aircraft_fk={aircraft_id}&category_type=COA"
    )
    assert hist.status_code == 200
    hist_data = hist.json()
    assert hist_data["total"] >= 1
    snap = next(
        (
            h
            for h in hist_data["items"]
            if h["date_of_expiration"] == certificate_payload["date_of_expiration"]
            and h["web_link"] == certificate_payload["web_link"]
        ),
        None,
    )
    assert snap is not None
    assert snap.get("asc_history") == cert_id


def test_create_same_aircraft_category_second_post_upserts_single_row(
    client: TestClient, certificate_payload: dict
):
    """Same aircraft and category_type: second POST updates the existing certificate (one row)."""
    first = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(certificate_payload)},
        files={},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    other = {**certificate_payload, "date_of_expiration": "2027-01-15"}
    second = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(other)},
        files={},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first_id
    assert second.json()["date_of_expiration"] == "2027-01-15"

    listed = client.get("/api/v1/aircraft-statutory-certificates/paged?limit=100&page=1")
    assert listed.status_code == 200
    same_type = [
        i
        for i in listed.json()["items"]
        if i["aircraft_fk"] == certificate_payload["aircraft_fk"]
        and i["category_type"] == certificate_payload["category_type"]
    ]
    assert len(same_type) == 1
