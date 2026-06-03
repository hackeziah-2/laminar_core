"""Advisory GET detail and PUT renew endpoints."""

from fastapi.testclient import TestClient

from app.models.personnel_compliance import PersonnelComplianceItemType


def test_advisory_get_and_renew_personnel_compliance(
    client: TestClient,
    client_with_regulatory_compliance_auth: TestClient,
):
    auth_client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Adv",
        "last_name": "RenewUser",
        "username": "advrenew_user",
        "password": "securepassword123",
        "status": True,
    }
    r = auth_client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    compliance_payload = {
        "account_information_id": account_id,
        "item_type": PersonnelComplianceItemType.AUTH_EXPIRY.value,
        "auth_issue_date": "2024-01-15",
        "expiry_date": "2026-06-30",
        "is_withhold": False,
    }
    r2 = auth_client.post("/api/v1/personnel-compliance/", json=compliance_payload)
    assert r2.status_code == 201, r2.text
    compliance_id = r2.json()["id"]

    r3 = client.get(
        f"/api/v1/advisory/{compliance_id}/",
        params={"regulatory_compliance": "personnel-compliance"},
    )
    assert r3.status_code == 200, r3.text
    detail = r3.json()
    assert detail["expiry_date"] == "2026-06-30"
    assert detail["auth_issue_date"] == "2024-01-15"
    assert detail["web_link"] == ""

    renew_body = {
        "regulatory_compliance": "personnel-compliance",
        "expiry_date": "2027-12-31",
        "auth_issue_date": "2025-03-01",
    }
    r4 = auth_client.put(
        f"/api/v1/advisory/{compliance_id}/renew/",
        json=renew_body,
    )
    assert r4.status_code == 200, r4.text
    renewed = r4.json()
    assert renewed["expiry_date"] == "2027-12-31"
    assert renewed["auth_issue_date"] == "2025-03-01"
    assert renewed["web_link"] == ""

    r5 = client.get(
        f"/api/v1/advisory/{compliance_id}/",
        params={"regulatory_compliance": "personnel-compliance"},
    )
    assert r5.status_code == 200, r5.text
    assert r5.json()["expiry_date"] == "2027-12-31"
    assert r5.json()["auth_issue_date"] == "2025-03-01"
