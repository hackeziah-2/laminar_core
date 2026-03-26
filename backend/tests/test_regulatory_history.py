"""Tests for organizational approvals history and aircraft statutory certificates history APIs."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def certificate_category_id(client: TestClient) -> int:
    response = client.post(
        "/api/v1/certificate-category-types/",
        json={"name": "History Test Category"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_org_approval_history_list_empty(client: TestClient):
    response = client.get("/api/v1/organizational-approvals-history/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_org_approval_history_create_and_get(
    client: TestClient, certificate_category_id: int
):
    payload = {
        "certificate_fk": certificate_category_id,
        "number": "HIST-001",
        "date_of_expiration": "2027-01-15",
        "web_link": "https://example.com/hist",
    }
    create = client.post("/api/v1/organizational-approvals-history/", json=payload)
    assert create.status_code == 201, create.text
    row = create.json()
    assert row["certificate_fk"] == certificate_category_id
    assert row["number"] == "HIST-001"
    hid = row["id"]

    got = client.get(f"/api/v1/organizational-approvals-history/{hid}")
    assert got.status_code == 200
    assert got.json()["id"] == hid

    paged = client.get(
        f"/api/v1/organizational-approvals-history/paged?certificate_fk={certificate_category_id}"
    )
    assert paged.status_code == 200
    assert paged.json()["total"] >= 1


def test_org_approval_history_not_found(client: TestClient):
    response = client.get("/api/v1/organizational-approvals-history/999999")
    assert response.status_code == 404


def test_aircraft_cert_history_list_empty(client: TestClient):
    response = client.get("/api/v1/aircraft-statutory-certificates-history/paged?limit=10&page=1")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_aircraft_cert_history_create_and_get(client: TestClient, aircraft_id: int):
    payload = {
        "aircraft_fk": aircraft_id,
        "category_type": "COA",
        "date_of_expiration": "2028-06-01",
        "web_link": "https://example.com/cert-hist",
    }
    create = client.post("/api/v1/aircraft-statutory-certificates-history/", json=payload)
    assert create.status_code == 201, create.text
    row = create.json()
    assert row["aircraft_fk"] == aircraft_id
    assert row["category_type"] == "COA"
    hid = row["id"]

    got = client.get(f"/api/v1/aircraft-statutory-certificates-history/{hid}")
    assert got.status_code == 200
    assert got.json()["id"] == hid

    paged = client.get(
        f"/api/v1/aircraft-statutory-certificates-history/paged?aircraft_fk={aircraft_id}"
    )
    assert paged.status_code == 200
    assert paged.json()["total"] >= 1


def test_aircraft_cert_history_not_found(client: TestClient):
    response = client.get("/api/v1/aircraft-statutory-certificates-history/999999")
    assert response.status_code == 404
