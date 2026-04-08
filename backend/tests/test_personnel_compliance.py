"""Personnel compliance API tests; ensures nested account_information.full_name is always populated."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.models.personnel_compliance import PersonnelComplianceItemType
from app.schemas.personnel_compliance_schema import PersonnelComplianceRead


def test_personnel_compliance_paged_includes_nonempty_account_full_name(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Jane",
        "last_name": "Pilot",
        "username": "jpilot_pc",
        "password": "securepassword123",
        "status": True,
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    compliance_payload = {
        "account_information_id": account_id,
        "item_type": PersonnelComplianceItemType.CAAP_LICENSE.value,
        "is_withhold": False,
    }
    r2 = client.post("/api/v1/personnel-compliance/", json=compliance_payload)
    assert r2.status_code == 201, r2.text
    created = r2.json()
    assert created["account_information"] is not None
    assert created["account_information"]["full_name"] == "Pilot, Jane"

    r3 = client.get("/api/v1/personnel-compliance/paged?page=1&limit=10")
    assert r3.status_code == 200, r3.text

    r4 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=10&sort=expiry_date"
    )
    assert r4.status_code == 200, r4.text
    r5 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=10&sort=-EXPIRY_DATE"
    )
    assert r5.status_code == 200, r5.text
    body = r3.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["id"] == created["id"])
    assert item["account_information"] is not None
    fn = item["account_information"]["full_name"]
    assert fn is not None
    assert str(fn).strip() != ""
    assert fn == "Pilot, Jane"


def test_personnel_compliance_create_rejects_duplicate_account_and_item_type(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Dup",
        "last_name": "User",
        "username": "dupuser_pc",
        "password": "securepassword123",
        "status": True,
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    compliance_payload = {
        "account_information_id": account_id,
        "item_type": PersonnelComplianceItemType.HF_TRAINING.value,
        "is_withhold": False,
    }
    r1 = client.post("/api/v1/personnel-compliance/", json=compliance_payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/api/v1/personnel-compliance/", json=compliance_payload)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == 'Entry Already Exists "HF_TRAINING"'


def test_personnel_compliance_read_from_orm_full_name_from_first_last():
    """Regression: ORM-like nested account must produce last_name, first_name style full_name."""
    account = SimpleNamespace(
        id=1,
        first_name="Alan",
        last_name="Smith",
        middle_name=None,
        designation="Pilot",
        auth_stamp="ABC",
        license_no="L1",
    )
    pc = SimpleNamespace(
        id=10,
        account_information_id=1,
        item_type=PersonnelComplianceItemType.HF_TRAINING,
        authorization_scope_cessna_id=None,
        authorization_scope_baron_id=None,
        authorization_scope_others_id=None,
        auth_issue_date=None,
        expiry_date=None,
        is_withhold=False,
        created_at=None,
        updated_at=None,
        account_information=account,
        authorization_scope_cessna=None,
        authorization_scope_baron=None,
        authorization_scope_others=None,
    )
    read = PersonnelComplianceRead.from_orm(pc)
    assert read.account_information is not None
    assert read.account_information.full_name == "Smith, Alan"


def test_account_information_personnel_summary_full_name_with_middle():
    from app.schemas.personnel_authorization_schema import AccountInformationPersonnelSummary

    row = {
        "id": 3,
        "first_name": "Bob",
        "last_name": "Jones",
        "middle_name": "M",
        "designation": None,
        "auth_stamp": None,
        "license_no": None,
    }
    s = AccountInformationPersonnelSummary.parse_obj(row)
    assert s.full_name == "Jones, Bob, M"


def test_personnel_compliance_read_dict_roundtrip_keeps_account_full_name():
    """FastAPI re-validates response_model from dict(); nested summary dict has full_name but not first/last."""
    account = SimpleNamespace(
        id=1,
        first_name="Jane",
        last_name="Pilot",
        middle_name=None,
        designation=None,
        auth_stamp=None,
        license_no=None,
    )
    pc = SimpleNamespace(
        id=10,
        account_information_id=1,
        item_type=PersonnelComplianceItemType.CAAP_LICENSE,
        authorization_scope_cessna_id=None,
        authorization_scope_baron_id=None,
        authorization_scope_others_id=None,
        auth_issue_date=None,
        expiry_date=None,
        is_withhold=False,
        created_at=None,
        updated_at=None,
        account_information=account,
        authorization_scope_cessna=None,
        authorization_scope_baron=None,
        authorization_scope_others=None,
    )
    read = PersonnelComplianceRead.from_orm(pc)
    again = PersonnelComplianceRead.parse_obj(read.dict())
    assert again.account_information is not None
    assert again.account_information.full_name == "Pilot, Jane"
