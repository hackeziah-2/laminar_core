"""Pytest for AD Monitoring REST API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ad_monitoring_payload(aircraft_id: int) -> dict:
    """Minimal create payload for one AD monitoring record."""
    return {
        "aircraft_fk": aircraft_id,
        "ad_number": "AD-2024-0001",
        "subject": "Test subject",
        "inspection_interval": "100 FH",
    }


def test_ad_monitoring_web_link_crud(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Create/update/get optional web_link on global and aircraft-scoped endpoints."""
    create_payload = {
        **ad_monitoring_payload,
        "web_link": "https://example.com/ad/initial",
    }
    create_response = client.post(
        "/api/v1/ad-monitoring/",
        json=create_payload,
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    ad_id = created["id"]
    assert created["web_link"] == create_payload["web_link"]

    get_response = client.get(f"/api/v1/ad-monitoring/{ad_id}")
    assert get_response.status_code == 200
    assert get_response.json()["web_link"] == create_payload["web_link"]

    update_payload = {"web_link": "https://example.com/ad/updated"}
    update_response = client.put(
        f"/api/v1/ad-monitoring/{ad_id}",
        json=update_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["web_link"] == update_payload["web_link"]

    scoped_get = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}",
    )
    assert scoped_get.status_code == 200
    assert scoped_get.json()["web_link"] == update_payload["web_link"]

    scoped_update = client.put(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}",
        json={"web_link": "https://example.com/ad/scoped"},
    )
    assert scoped_update.status_code == 200
    assert scoped_update.json()["web_link"] == "https://example.com/ad/scoped"


def test_ad_monitoring_web_link_optional(
    client: TestClient,
    ad_monitoring_payload: dict,
):
    """web_link may be omitted on create."""
    response = client.post(
        "/api/v1/ad-monitoring/",
        json=ad_monitoring_payload,
    )
    assert response.status_code == 201, response.text
    assert response.json()["web_link"] is None
