"""Personnel compliance matrix v2: one paged row per account (merged authorization)."""

from datetime import date

from fastapi.testclient import TestClient


def test_personnel_compliance_matrix_2_paged_one_row_per_account_latest_auth(client: TestClient):
    account_data = {
        "first_name": "M2",
        "last_name": "MatrixUniqueRow",
        "username": "m2_matrix_unique",
        "password": "securepassword123",
        "status": True,
        "designation": "Captain",
        "license_no": "ATPL-99",
        "auth_stamp": "AUTH-M2-001",
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    pa1 = {
        "account_information_id": account_id,
        "caap_license_expiry": "2020-01-01",
        "is_withhold": False,
    }
    r1 = client.post("/api/v1/personnel-authorization/", json=pa1)
    assert r1.status_code == 201, r1.text

    pa2 = {
        "account_information_id": account_id,
        "caap_license_expiry": "2030-06-15",
        "auth_issue_date": "2025-01-10",
        "is_withhold": False,
    }
    r2 = client.post("/api/v1/personnel-authorization/", json=pa2)
    assert r2.status_code == 201, r2.text

    r3 = client.get(
        "/api/v1/personnel-compliance-matrix-2/paged?page=1&limit=50&search=MatrixUniqueRow"
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["account_information_id"] == account_id
    assert row["authorization_no"] == "AUTH-M2-001"
    assert row["name"] == "MatrixUniqueRow, M2"
    assert row["position"] == "Captain"
    assert row["lic_no_type"] == "ATPL-99"
    assert row["auth_issue_date"] == "2025-01-10"
    assert row["caap_lic_expiry"] == "2030-06-15"


def test_personnel_compliance_matrix_2_from_personnel_authorization_fallback_auth_doi():
    from types import SimpleNamespace

    from app.schemas.personnel_compliance_matrix_2_schema import PersonnelComplianceMatrix2Item

    acc = SimpleNamespace(
        id=1,
        first_name="A",
        last_name="B",
        middle_name=None,
        designation="P",
        auth_stamp="S",
        license_no="L",
        auth_initial_doi=date(2019, 1, 1),
    )
    pa = SimpleNamespace(
        account_information_id=1,
        auth_initial_doi=None,
        auth_issue_date=None,
        auth_expiry_date=None,
        authorization_scope_cessna=None,
        authorization_scope_baron=None,
        authorization_scope_others=None,
        caap_license_expiry=None,
        human_factors_training_expiry=None,
        type_training_expiry_cessna=None,
        type_training_expiry_baron=None,
        account_information=acc,
    )
    item = PersonnelComplianceMatrix2Item.from_personnel_authorization(pa)
    assert item.auth_initial_doi == date(2019, 1, 1)
