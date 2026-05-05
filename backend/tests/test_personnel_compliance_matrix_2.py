"""Personnel compliance matrix v2: one paged row per account (merged authorization)."""

from datetime import date

from fastapi.testclient import TestClient


def test_personnel_compliance_matrix_2_paged_one_row_per_account_latest_auth(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
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
    r3b = client.get(
        "/api/v1/personnel-compliance-matrix-2?page=1&limit=50&search=MatrixUniqueRow"
    )
    assert r3b.status_code == 200, r3b.text
    assert r3b.json() == r3.json()
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


def test_personnel_compliance_matrix_2_paged_row_when_only_personnel_compliance_no_pa(
    client_with_regulatory_compliance_auth: TestClient,
):
    """Accounts with matrix-type compliance but no personnel_authorization still appear."""
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Only",
        "last_name": "ComplianceNoPA",
        "username": "m2_pc_only",
        "password": "securepassword123",
        "status": True,
        "designation": "Captain",
        "license_no": "ATPL-PC",
        "auth_stamp": "AUTH-PC-ONLY",
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    pc = {
        "account_information_id": account_id,
        "item_type": "CAAP_LICENSE",
        "expiry_date": "2029-11-11",
        "is_withhold": False,
    }
    r_pc = client.post("/api/v1/personnel-compliance/", json=pc)
    assert r_pc.status_code == 201, r_pc.text

    r3 = client.get(
        "/api/v1/personnel-compliance-matrix-2/paged?page=1&limit=50&search=ComplianceNoPA"
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["total"] >= 1
    match = [it for it in body["items"] if it["account_information_id"] == account_id]
    assert len(match) == 1
    assert match[0]["caap_lic_expiry"] == "2029-11-11"
    assert match[0]["authorization_no"] == "AUTH-PC-ONLY"


def test_personnel_compliance_matrix_2_paged_others_expiry_from_compliance_others(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "O",
        "last_name": "OthersExpiryMatrix",
        "username": "m2_others_exp",
        "password": "securepassword123",
        "status": True,
        "designation": "FO",
        "license_no": "CPL-1",
        "auth_stamp": "AUTH-M2-OE",
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    pa = {
        "account_information_id": account_id,
        "is_withhold": False,
    }
    r_pa = client.post("/api/v1/personnel-authorization/", json=pa)
    assert r_pa.status_code == 201, r_pa.text

    pc = {
        "account_information_id": account_id,
        "item_type": "OTHERS",
        "expiry_date": "2028-03-01",
        "is_withhold": False,
    }
    r_pc = client.post("/api/v1/personnel-compliance/", json=pc)
    assert r_pc.status_code == 201, r_pc.text

    r3 = client.get(
        "/api/v1/personnel-compliance-matrix-2/paged?page=1&limit=50&search=OthersExpiryMatrix"
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["others_expiry_date"] == "2028-03-01"


def test_personnel_compliance_matrix_date_by_item_type():
    from types import SimpleNamespace

    from app.models.personnel_compliance import PersonnelComplianceItemType
    from app.schemas.personnel_compliance_matrix_2_schema import (
        _coalesce_compliance_then_auth,
        _personnel_compliance_matrix_date,
    )

    pc_auth = SimpleNamespace(
        item_type=PersonnelComplianceItemType.AUTH_EXPIRY,
        auth_issue_date=date(2026, 1, 15),
        expiry_date=date(2099, 1, 1),
    )
    assert _personnel_compliance_matrix_date(pc_auth) == date(2026, 1, 15)

    pc_caap = SimpleNamespace(
        item_type=PersonnelComplianceItemType.CAAP_LICENSE,
        auth_issue_date=date(2020, 1, 1),
        expiry_date=date(2027, 6, 1),
    )
    assert _personnel_compliance_matrix_date(pc_caap) == date(2027, 6, 1)

    assert _coalesce_compliance_then_auth(pc_caap, date(2030, 1, 1)) == date(2027, 6, 1)
    assert _coalesce_compliance_then_auth(None, date(2030, 1, 1)) == date(2030, 1, 1)


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
    assert item.others_expiry_date is None

    item2 = PersonnelComplianceMatrix2Item.from_personnel_authorization(
        pa, others_expiry_date=date(2027, 1, 2)
    )
    assert item2.others_expiry_date == date(2027, 1, 2)
