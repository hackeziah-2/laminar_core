"""Tests for organizational approvals history and aircraft statutory certificates history APIs."""
import json

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
    approval_resp = client.post(
        "/api/v1/organizational-approvals/",
        json={
            "json_data": {
                "certificate_fk": certificate_category_id,
                "number": "HIST-001",
                "date_of_expiration": "2027-01-15",
                "web_link": "https://example.com/approval",
                "is_withhold": False,
            }
        },
    )
    assert approval_resp.status_code == 201, approval_resp.text
    approval_id = approval_resp.json()["id"]

    payload = {
        "certificate_fk": certificate_category_id,
        "oa_history": approval_id,
        "number": "HIST-001",
        "date_of_expiration": "2027-01-15",
        "web_link": "https://example.com/hist",
    }
    create = client.post("/api/v1/organizational-approvals-history/", json=payload)
    assert create.status_code == 201, create.text
    row = create.json()
    assert row["certificate_fk"] == certificate_category_id
    assert row["number"] == "HIST-001"
    assert row["oa_history"] == approval_id
    hid = row["id"]

    got = client.get(f"/api/v1/organizational-approvals-history/{hid}")
    assert got.status_code == 200
    assert got.json()["id"] == hid
    assert got.json()["oa_history"] == approval_id

    paged = client.get(
        f"/api/v1/organizational-approvals-history/paged?certificate_fk={certificate_category_id}"
    )
    assert paged.status_code == 200
    assert paged.json()["total"] >= 1

    paged_by_oa = client.get(
        f"/api/v1/organizational-approvals-history/paged?oa_history={approval_id}"
    )
    assert paged_by_oa.status_code == 200
    assert all(i["oa_history"] == approval_id for i in paged_by_oa.json()["items"])

    paged_path = client.get(
        f"/api/v1/organizational-approvals-history/{approval_id}/paged?limit=10&page=1"
    )
    assert paged_path.status_code == 200
    path_data = paged_path.json()
    assert path_data["total"] >= 1
    assert all(i["oa_history"] == approval_id for i in path_data["items"])


def test_org_approval_history_create_resolves_oa_history_from_natural_key(
    client: TestClient, certificate_category_id: int
):
    appr = client.post(
        "/api/v1/organizational-approvals/",
        json={
            "json_data": {
                "certificate_fk": certificate_category_id,
                "number": "AUTO-OA-001",
                "date_of_expiration": "2028-02-01",
                "web_link": "https://example.com/a",
                "is_withhold": False,
            }
        },
    )
    assert appr.status_code == 201, appr.text
    expected_oa_id = appr.json()["id"]
    payload = {
        "certificate_fk": certificate_category_id,
        "number": "AUTO-OA-001",
        "date_of_expiration": "2028-02-01",
        "web_link": "https://example.com/hist-snap",
    }
    create = client.post("/api/v1/organizational-approvals-history/", json=payload)
    assert create.status_code == 201, create.text
    row = create.json()
    assert row["oa_history"] == expected_oa_id


def test_org_approval_history_not_found(client: TestClient):
    response = client.get("/api/v1/organizational-approvals-history/999999")
    assert response.status_code == 404


def test_aircraft_cert_history_list_empty(client: TestClient):
    response = client.get("/api/v1/aircraft-statutory-certificates-history/paged?limit=10&page=1")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_aircraft_cert_history_create_and_get(client: TestClient, aircraft_id: int):
    cert_payload = {
        "aircraft_fk": aircraft_id,
        "category_type": "COR",
        "date_of_expiration": "2028-05-01",
        "web_link": "https://example.com/cert",
        "file_path": None,
    }
    cert_resp = client.post(
        "/api/v1/aircraft-statutory-certificates/",
        data={"json_data": json.dumps(cert_payload)},
        files={},
    )
    assert cert_resp.status_code == 201, cert_resp.text
    cert_id = cert_resp.json()["id"]

    payload = {
        "aircraft_fk": aircraft_id,
        "asc_history": cert_id,
        "category_type": "COA",
        "date_of_expiration": "2028-06-01",
        "web_link": "https://example.com/cert-hist",
    }
    create = client.post("/api/v1/aircraft-statutory-certificates-history/", json=payload)
    assert create.status_code == 201, create.text
    row = create.json()
    assert row["aircraft_fk"] == aircraft_id
    assert row["asc_history"] == cert_id
    assert row["category_type"] == "COA"
    hid = row["id"]

    got = client.get(f"/api/v1/aircraft-statutory-certificates-history/{hid}")
    assert got.status_code == 200
    assert got.json()["id"] == hid
    assert got.json()["asc_history"] == cert_id

    paged = client.get(
        f"/api/v1/aircraft-statutory-certificates-history/paged?aircraft_fk={aircraft_id}"
    )
    assert paged.status_code == 200
    assert paged.json()["total"] >= 1

    paged_by_asc = client.get(
        f"/api/v1/aircraft-statutory-certificates-history/paged?asc_history={cert_id}"
    )
    assert paged_by_asc.status_code == 200
    assert all(i["asc_history"] == cert_id for i in paged_by_asc.json()["items"])

    paged_by_asc_path = client.get(
        f"/api/v1/aircraft-statutory-certificates-history/{cert_id}/paged?limit=10&page=1"
    )
    assert paged_by_asc_path.status_code == 200
    paged_path_data = paged_by_asc_path.json()
    assert paged_path_data["total"] >= 1
    assert all(i["asc_history"] == cert_id for i in paged_path_data["items"])


def test_aircraft_cert_history_not_found(client: TestClient):
    response = client.get("/api/v1/aircraft-statutory-certificates-history/999999")
    assert response.status_code == 404
