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
    assert created["account_information"]["full_name"] == "PILOT, JANE"

    r3 = client.get("/api/v1/personnel-compliance/paged?page=1&page_size=50")
    assert r3.status_code == 200, r3.text

    r4 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&page_size=50&sort=expiry_date"
    )
    assert r4.status_code == 200, r4.text
    r5 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&page_size=50&sort=-EXPIRY_DATE"
    )
    assert r5.status_code == 200, r5.text
    body = r3.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["id"] == created["id"])
    assert item["account_information"] is not None
    fn = item["account_information"]["full_name"]
    assert fn is not None
    assert str(fn).strip() != ""
    assert fn == "PILOT, JANE"


def test_personnel_compliance_paged_includes_auth_initial_doi_from_latest_personnel_authorization(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Auth",
        "last_name": "DoiUser",
        "username": "authdoi_pc",
        "password": "securepassword123",
        "status": True,
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    pa_old = {
        "account_information_id": account_id,
        "auth_initial_doi": "2018-05-01",
        "is_withhold": False,
    }
    r1 = client.post("/api/v1/personnel-authorization/", json=pa_old)
    assert r1.status_code == 201, r1.text

    pa_new = {
        "account_information_id": account_id,
        "auth_initial_doi": "2024-03-15",
        "is_withhold": False,
    }
    r2 = client.post("/api/v1/personnel-authorization/", json=pa_new)
    assert r2.status_code == 201, r2.text

    compliance_payload = {
        "account_information_id": account_id,
        "item_type": PersonnelComplianceItemType.AUTH_EXPIRY.value,
        "is_withhold": False,
    }
    r3 = client.post("/api/v1/personnel-compliance/", json=compliance_payload)
    assert r3.status_code == 201, r3.text
    created_id = r3.json()["id"]

    r4 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=50&search=DoiUser"
    )
    assert r4.status_code == 200, r4.text
    item = next(i for i in r4.json()["items"] if i["id"] == created_id)
    assert item["auth_initial_doi"] == "2024-03-15"

    r5 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=50&sort=auth_initial_doi"
    )
    assert r5.status_code == 200, r5.text
    r6 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=50&sort=-auth_initial_doi"
    )
    assert r6.status_code == 200, r6.text


def test_personnel_compliance_paged_auth_initial_doi_falls_back_to_account(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Acct",
        "last_name": "DoiOnly",
        "username": "acctdoi_pc",
        "password": "securepassword123",
        "status": True,
        "auth_initial_doi": "2019-06-20",
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
    created_id = r2.json()["id"]

    r3 = client.get(
        "/api/v1/personnel-compliance/paged?page=1&limit=50&search=DoiOnly"
    )
    assert r3.status_code == 200, r3.text
    item = next(i for i in r3.json()["items"] if i["id"] == created_id)
    assert item["auth_initial_doi"] == "2019-06-20"


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


def test_personnel_compliance_piper_pa34_crud_filter_and_existing_types(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth
    account_data = {
        "first_name": "Piper",
        "last_name": "Pa34User",
        "username": "piper_pa34_pc",
        "password": "securepassword123",
        "status": True,
    }
    r = client.post("/api/v1/account-information/", json=account_data)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    piper_payload = {
        "account_information_id": account_id,
        "item_type": PersonnelComplianceItemType.PIPER_PA_34.value,
        "expiry_date": "2028-04-15",
        "is_withhold": False,
    }
    created = client.post("/api/v1/personnel-compliance/", json=piper_payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["item_type"] == "PIPER PA-34"
    created_id = body["id"]

    fetched = client.get(f"/api/v1/personnel-compliance/{created_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["item_type"] == "PIPER PA-34"

    paged = client.get("/api/v1/personnel-compliance/paged?page=1&limit=50")
    assert paged.status_code == 200, paged.text
    paged_item = next(i for i in paged.json()["items"] if i["id"] == created_id)
    assert paged_item["item_type"] == "PIPER PA-34"

    updated = client.put(
        f"/api/v1/personnel-compliance/{created_id}",
        json={
            "item_type": "PIPER PA-34",
            "expiry_date": "2029-01-31",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["item_type"] == "PIPER PA-34"
    assert updated.json()["expiry_date"] == "2029-01-31"

    filtered = client.get(
        "/api/v1/personnel-compliance/",
        params={"item_type": "PIPER PA-34", "page": 1, "limit": 50},
    )
    assert filtered.status_code == 200, filtered.text
    filtered_ids = {i["id"] for i in filtered.json()["items"]}
    assert created_id in filtered_ids
    assert all(i["item_type"] == "PIPER PA-34" for i in filtered.json()["items"])

    cessna_account = {
        "first_name": "Cessna",
        "last_name": "StillWorks",
        "username": "cessna_still_pc",
        "password": "securepassword123",
        "status": True,
    }
    r_c = client.post("/api/v1/account-information/", json=cessna_account)
    assert r_c.status_code == 201, r_c.text
    cessna = client.post(
        "/api/v1/personnel-compliance/",
        json={
            "account_information_id": r_c.json()["id"],
            "item_type": PersonnelComplianceItemType.CESSNA.value,
            "is_withhold": False,
        },
    )
    assert cessna.status_code == 201, cessna.text
    assert cessna.json()["item_type"] == "CESSNA"

    baron_account = {
        "first_name": "Baron",
        "last_name": "StillWorks",
        "username": "baron_still_pc",
        "password": "securepassword123",
        "status": True,
    }
    r_b = client.post("/api/v1/account-information/", json=baron_account)
    assert r_b.status_code == 201, r_b.text
    baron = client.post(
        "/api/v1/personnel-compliance/",
        json={
            "account_information_id": r_b.json()["id"],
            "item_type": PersonnelComplianceItemType.BARON.value,
            "is_withhold": False,
        },
    )
    assert baron.status_code == 201, baron.text
    assert baron.json()["item_type"] == "BARON"


def test_personnel_compliance_paged_search_matches_name_auth_and_license(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth

    def create_account(**fields):
        payload = {
            "password": "securepassword123",
            "status": True,
            **fields,
        }
        created = client.post("/api/v1/account-information/", json=payload)
        assert created.status_code == 201, created.text
        return created.json()["id"]

    alpha_id = create_account(
        first_name="Searchable",
        last_name="AlphaPerson",
        username="search_alpha_pc",
        auth_stamp="AUTH-ALPHA-77",
        license_no="LIC-ALPHA-42",
    )
    beta_id = create_account(
        first_name="Other",
        last_name="BetaPerson",
        username="search_beta_pc",
        auth_stamp="AUTH-BETA-88",
        license_no="LIC-BETA-99",
    )
    for account_id in (alpha_id, beta_id):
        created = client.post(
            "/api/v1/personnel-compliance/",
            json={
                "account_information_id": account_id,
                "item_type": PersonnelComplianceItemType.HF_TRAINING.value,
                "is_withhold": False,
            },
        )
        assert created.status_code == 201, created.text

    def listed_account_ids(query: str) -> list[int]:
        response = client.get(f"/api/v1/personnel-compliance/paged?{query}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["page"] == 1
        assert body["total"] == len(body["items"])
        return [item["account_information_id"] for item in body["items"]]

    assert listed_account_ids("page=1&page_size=50&name=alphaperson") == [alpha_id]
    assert listed_account_ids("page=1&page_size=50&name=alpha-77") == [alpha_id]
    assert listed_account_ids("page=1&page_size=50&search=lic-alpha") == [alpha_id]
    assert (
        listed_account_ids(
            "page=1&page_size=50&name=alphaperson&item_type=CESSNA"
        )
        == []
    )
    filtered = client.get(
        "/api/v1/personnel-compliance/paged?page=1&page_size=50&name=alphaperson&item_type=HF_TRAINING"
    )
    assert filtered.status_code == 200, filtered.text
    filtered_body = filtered.json()
    assert filtered_body["total"] == 1
    assert filtered_body["page"] == 1
    assert filtered_body["items"][0]["account_information_id"] == alpha_id


def test_personnel_compliance_paged_sorts_by_authorization_number(
    client_with_regulatory_compliance_auth: TestClient,
):
    client = client_with_regulatory_compliance_auth

    def create_account(username: str, auth_stamp: str) -> int:
        created = client.post(
            "/api/v1/account-information/",
            json={
                "first_name": "Sort",
                "last_name": "AuthOrder",
                "username": username,
                "password": "securepassword123",
                "status": True,
                "auth_stamp": auth_stamp,
            },
        )
        assert created.status_code == 201, created.text
        account_id = created.json()["id"]
        compliance = client.post(
            "/api/v1/personnel-compliance/",
            json={
                "account_information_id": account_id,
                "item_type": PersonnelComplianceItemType.HF_TRAINING.value,
                "is_withhold": False,
            },
        )
        assert compliance.status_code == 201, compliance.text
        return account_id

    later_id = create_account("sort_auth_b_pc", "AUTH-SORT-B")
    earlier_id = create_account("sort_auth_a_pc", "AUTH-SORT-A")

    def ordered_ids(sort: str) -> list[int]:
        response = client.get(
            "/api/v1/personnel-compliance/paged"
            f"?page=1&page_size=50&name=authorder&sort={sort}"
        )
        assert response.status_code == 200, response.text
        return [item["account_information_id"] for item in response.json()["items"]]

    assert ordered_ids("authorization_no") == [earlier_id, later_id]
    assert ordered_ids("-authorization_no") == [later_id, earlier_id]
