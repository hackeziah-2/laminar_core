"""Authorization scope Piper CRUD at /api/v1/authorization-scope-piper."""
from fastapi.testclient import TestClient


def test_authorization_scope_piper_crud_list_paged_and_personnel_alias(
    client: TestClient,
):
    created = client.post(
        "/api/v1/authorization-scope-piper/",
        json={"name": "PA-34-200T"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "PA-34-200T"
    scope_id = body["id"]
    assert scope_id > 0

    duplicate = client.post(
        "/api/v1/authorization-scope-piper/",
        json={"name": "PA-34-200T"},
    )
    assert duplicate.status_code == 400

    listed = client.get("/api/v1/authorization-scope-piper/list")
    assert listed.status_code == 200, listed.text
    names = [row["name"] for row in listed.json()]
    assert "PA-34-200T" in names

    paged = client.get("/api/v1/authorization-scope-piper/paged?page=1&page_size=50")
    assert paged.status_code == 200, paged.text
    payload = paged.json()
    assert payload["total"] >= 1
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["pages"] >= 1
    assert any(item["id"] == scope_id for item in payload["items"])

    fetched = client.get(f"/api/v1/authorization-scope-piper/{scope_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["name"] == "PA-34-200T"

    updated = client.put(
        f"/api/v1/authorization-scope-piper/{scope_id}",
        json={"name": "PA-34-220T"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "PA-34-220T"

    account = client.post(
        "/api/v1/account-information/",
        json={
            "first_name": "Piper",
            "last_name": "Scope",
            "username": "piper_scope_user",
            "password": "securepassword123",
            "status": True,
        },
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]

    pa = client.post(
        "/api/v1/personnel-authorization/",
        json={
            "account_information_id": account_id,
            "authorization_scope_piper_id": scope_id,
            "is_withhold": False,
        },
    )
    assert pa.status_code == 201, pa.text
    pa_body = pa.json()
    assert pa_body["authorization_scope_piper_pa34_id"] == scope_id
    assert pa_body["authorization_scope_piper_pa34"]["id"] == scope_id
    assert pa_body["authorization_scope_piper_pa34"]["name"] == "PA-34-220T"

    deleted = client.delete(f"/api/v1/authorization-scope-piper/{scope_id}")
    assert deleted.status_code == 204, deleted.text

    missing = client.get(f"/api/v1/authorization-scope-piper/{scope_id}")
    assert missing.status_code == 404
