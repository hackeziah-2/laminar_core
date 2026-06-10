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


def test_work_order_ad_monitoring_create_writes_audit_log(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Work-order AD monitoring create should persist a CREATE audit log."""
    from app.constants.audit import WORK_ORDER_AD_MONITORING_MODULE_NAME

    ad_response = client.post("/api/v1/ad-monitoring/", json=ad_monitoring_payload)
    assert ad_response.status_code == 201, ad_response.text
    ad_id = ad_response.json()["id"]

    wo_payload = {
        "ad_monitoring_fk": ad_id,
        "work_order_number": "WO-TEST-001",
        "atl_ref": "ATL-001",
    }
    create_response = client.post(
        "/api/v1/work-order-ad-monitoring/",
        json=wo_payload,
    )
    assert create_response.status_code == 201, create_response.text
    work_order_id = create_response.json()["id"]

    audit_response = client.get(
        "/api/v1/audit-logs/"
        f"?module_name={WORK_ORDER_AD_MONITORING_MODULE_NAME}&record_id={work_order_id}"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    create_logs = [item for item in payload["items"] if item["action"] == "CREATE"]
    assert len(create_logs) == 1
    assert create_logs[0]["table_name"] == "workorder_ad_monitoring"
    assert create_logs[0]["new_data"]["work_order_number"] == "WO-TEST-001"


def test_work_order_ad_monitoring_delete_writes_audit_log(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Work-order AD monitoring delete should persist a DELETE audit log."""
    from app.constants.audit import WORK_ORDER_AD_MONITORING_MODULE_NAME

    ad_response = client.post("/api/v1/ad-monitoring/", json=ad_monitoring_payload)
    assert ad_response.status_code == 201, ad_response.text
    ad_id = ad_response.json()["id"]

    wo_payload = {
        "ad_monitoring_fk": ad_id,
        "work_order_number": "WO-TEST-DEL",
        "atl_ref": "ATL-002",
    }
    create_response = client.post(
        "/api/v1/work-order-ad-monitoring/",
        json=wo_payload,
    )
    assert create_response.status_code == 201, create_response.text
    work_order_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/work-order-ad-monitoring/{work_order_id}"
    )
    assert delete_response.status_code == 204

    audit_response = client.get(
        "/api/v1/audit-logs/"
        f"?module_name={WORK_ORDER_AD_MONITORING_MODULE_NAME}"
        f"&record_id={work_order_id}&action=DELETE"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    delete_log = payload["items"][0]
    assert delete_log["action"] == "DELETE"
    assert delete_log["old_data"] is not None
    assert delete_log["new_data"] is None
