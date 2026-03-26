"""Pytest for organizational approvals REST API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def certificate_category_id(client: TestClient) -> int:
    response = client.post(
        "/api/v1/certificate-category-types/",
        json={"name": "Org Approval Test Category"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def approval_payload(certificate_category_id: int) -> dict:
    return {
        "certificate_fk": certificate_category_id,
        "number": "CERT-001",
        "date_of_expiration": "2026-12-31",
        "web_link": "https://example.com/approval",
        "is_withhold": False,
    }


def test_create_organizational_approval(
    client: TestClient, approval_payload: dict, certificate_category_id: int
):
    response = client.post(
        "/api/v1/organizational-approvals/",
        json={"json_data": approval_payload},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["certificate_fk"] == certificate_category_id
    assert data["number"] == "CERT-001"
    assert data["date_of_expiration"] == "2026-12-31"


def test_create_duplicate_organizational_approval_returns_409(
    client: TestClient, approval_payload: dict
):
    first = client.post(
        "/api/v1/organizational-approvals/",
        json={"json_data": approval_payload},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/organizational-approvals/",
        json={"json_data": approval_payload},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Entry already exists"


def test_create_same_cert_different_number_ok(
    client: TestClient, approval_payload: dict
):
    first = client.post(
        "/api/v1/organizational-approvals/",
        json={"json_data": approval_payload},
    )
    assert first.status_code == 201

    other = {**approval_payload, "number": "CERT-002"}
    second = client.post(
        "/api/v1/organizational-approvals/",
        json={"json_data": other},
    )
    assert second.status_code == 201
