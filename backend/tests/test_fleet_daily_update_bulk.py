"""Bulk partial update tests for Fleet Daily Update."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_account
from app.constants.audit import (
    FLEET_DAILY_UPDATE_MODULE_NAME as FLEET_DAILY_UPDATE_AUDIT_MODULE_NAME,
)
from app.main import app
from app.models.fleet_daily_update import FLEET_DAILY_UPDATE_MODULE_NAME
from tests.conftest import TestSessionLocal
from tests.factories.rbac import seed_account_with_module_permissions


@pytest.fixture(scope="function")
def client_with_daily_update_auth(client: TestClient):
    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            return await seed_account_with_module_permissions(
                session,
                {
                    FLEET_DAILY_UPDATE_MODULE_NAME: {
                        "can_read": True,
                        "can_update": True,
                    },
                },
            )

    account_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


def _create_aircraft(client: TestClient, registration: str) -> int:
    payload = {
        "registration": registration,
        "model": "172",
        "msn": f"MSN-{registration}",
        "base": "Test Base",
        "ownership": "Test Owner",
        "status": "Active",
    }
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(payload)},
        files={},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _fleet_update_id_for_aircraft(client: TestClient, aircraft_id: int) -> int:
    response = client.get(f"/api/v1/aircraft/{aircraft_id}/fleet-daily-update")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_bulk_update_fleet_daily_updates_success(
    client_with_daily_update_auth: TestClient,
):
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-BULK-001")
    ac2 = _create_aircraft(client, "FDU-BULK-002")
    update_id_1 = _fleet_update_id_for_aircraft(client, ac1)
    update_id_2 = _fleet_update_id_for_aircraft(client, ac2)

    response = client.patch(
        "/api/v1/fleet-daily-update/bulk/",
        json={
            "updates": [
                {
                    "id": update_id_1,
                    "status": "OPERATIONAL",
                    "tach_time_eod": 1234.5,
                    "remarks": "Updated after daily review",
                },
                {
                    "id": update_id_2,
                    "status": "AOG",
                    "remarks": "Grounded",
                },
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Fleet Daily Update records updated successfully"
    assert body["updated_count"] == 2
    assert set(body["updated_ids"]) == {update_id_1, update_id_2}

    r1 = client.get(f"/api/v1/fleet-daily-update/{update_id_1}")
    assert r1.status_code == 200
    assert r1.json()["status"] == "Operational"
    assert r1.json()["tach_time_eod"] == 1234.5
    assert r1.json()["remarks"] == "Updated after daily review"

    r2 = client.get(f"/api/v1/fleet-daily-update/{update_id_2}")
    assert r2.status_code == 200
    assert r2.json()["status"] == "AOG"
    assert r2.json()["remarks"] == "Grounded"


def test_bulk_update_fleet_daily_updates_missing_id_returns_404(
    client_with_daily_update_auth: TestClient,
):
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-BULK-404")
    update_id = _fleet_update_id_for_aircraft(client, ac1)

    response = client.patch(
        "/api/v1/fleet-daily-update/bulk/",
        json={
            "updates": [
                {"id": update_id, "remarks": "Should not persist alone if batch fails"},
                {"id": 999999, "remarks": "Missing record"},
            ]
        },
    )
    assert response.status_code == 404, response.text
    assert "999999" in response.text

    unchanged = client.get(f"/api/v1/fleet-daily-update/{update_id}")
    assert unchanged.status_code == 200
    assert unchanged.json()["remarks"] is None


def test_bulk_update_fleet_daily_updates_requires_can_update(client: TestClient):
    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            return await seed_account_with_module_permissions(
                session,
                {
                    FLEET_DAILY_UPDATE_MODULE_NAME: {
                        "can_read": True,
                        "can_update": False,
                    },
                },
            )

    account_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    try:
        ac1 = _create_aircraft(client, "FDU-BULK-DENY")
        update_id = _fleet_update_id_for_aircraft(client, ac1)

        response = client.patch(
            "/api/v1/fleet-daily-update/bulk/",
            json={"updates": [{"id": update_id, "remarks": "Denied"}]},
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.pop(get_current_active_account, None)


def test_bulk_update_fleet_daily_updates_writes_audit_logs(
    client_with_daily_update_auth: TestClient,
):
    """Bulk update should persist an UPDATE audit log per updated record."""
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-AUDIT-001")
    ac2 = _create_aircraft(client, "FDU-AUDIT-002")
    update_id_1 = _fleet_update_id_for_aircraft(client, ac1)
    update_id_2 = _fleet_update_id_for_aircraft(client, ac2)

    response = client.patch(
        "/api/v1/fleet-daily-update/bulk/",
        json={
            "updates": [
                {"id": update_id_1, "remarks": "Audit bulk update 1"},
                {"id": update_id_2, "status": "AOG", "remarks": "Audit bulk update 2"},
            ]
        },
    )
    assert response.status_code == 200, response.text

    all_logs = client.get("/api/v1/audit-logs/").json()
    fleet_update_logs = [
        item
        for item in all_logs["items"]
        if item.get("module_name") == FLEET_DAILY_UPDATE_AUDIT_MODULE_NAME
        and item.get("action") == "UPDATE"
    ]
    assert len(fleet_update_logs) >= 2

    for update_id, expected_remarks in (
        (update_id_1, "Audit bulk update 1"),
        (update_id_2, "Audit bulk update 2"),
    ):
        update_logs = [
            item
            for item in all_logs["items"]
            if item["module_name"] == FLEET_DAILY_UPDATE_AUDIT_MODULE_NAME
            and item["record_id"] == update_id
            and item["action"] == "UPDATE"
        ]
        assert len(update_logs) >= 1
        update_log = update_logs[0]
        assert update_log["action"] == "UPDATE"
        assert update_log["table_name"] == "fleet_daily_update"
        assert update_log["old_data"] is not None
        assert update_log["new_data"] is not None
        assert update_log["new_data"]["remarks"] == expected_remarks
        assert "remarks" in (update_log["changed_fields"] or [])


def test_bulk_update_fleet_daily_updates_calls_notification_once(
    client_with_daily_update_auth: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-NOTIF-001")
    ac2 = _create_aircraft(client, "FDU-NOTIF-002")
    update_id_1 = _fleet_update_id_for_aircraft(client, ac1)
    update_id_2 = _fleet_update_id_for_aircraft(client, ac2)

    calls = []

    async def _fake_bulk_notification(*args, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(
        "app.repository.fleet_daily_update.publish_fleet_daily_update_bulk_notification",
        _fake_bulk_notification,
    )

    response = client.patch(
        "/api/v1/fleet-daily-update/bulk/",
        json={
            "updates": [
                {"id": update_id_1, "remarks": "Notif bulk update 1"},
                {"id": update_id_2, "remarks": "Notif bulk update 2"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert len(calls[0]["updated_objects"]) == 2


def test_bulk_update_fleet_daily_updates_notification_failure_does_not_fail_response(
    client_with_daily_update_auth: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-NOTIF-ERR-001")
    update_id_1 = _fleet_update_id_for_aircraft(client, ac1)

    async def _fake_bulk_notification(*args, **kwargs):
        raise RuntimeError("notification failure")

    monkeypatch.setattr(
        "app.repository.fleet_daily_update.publish_fleet_daily_update_bulk_notification",
        _fake_bulk_notification,
    )

    response = client.patch(
        "/api/v1/fleet-daily-update/bulk/",
        json={"updates": [{"id": update_id_1, "remarks": "Notif error test"}]},
    )
    assert response.status_code == 200, response.text
    assert "Failed to publish Fleet Daily Update bulk update notification" in caplog.text


def test_fleet_daily_update_delete_writes_audit_log(
    client_with_daily_update_auth: TestClient,
):
    """Fleet Daily Update delete should persist a DELETE audit log after commit."""
    client = client_with_daily_update_auth
    ac1 = _create_aircraft(client, "FDU-AUDIT-DEL")
    update_id = _fleet_update_id_for_aircraft(client, ac1)

    delete_response = client.delete(f"/api/v1/fleet-daily-update/{update_id}")
    assert delete_response.status_code == 204

    all_logs = client.get("/api/v1/audit-logs/").json()
    delete_logs = [
        item
        for item in all_logs["items"]
        if item["module_name"] == FLEET_DAILY_UPDATE_AUDIT_MODULE_NAME
        and item["record_id"] == update_id
        and item["action"] == "DELETE"
    ]
    assert len(delete_logs) >= 1
    delete_log = delete_logs[0]
    assert delete_log["action"] == "DELETE"
    assert delete_log["old_data"] is not None
    assert delete_log["new_data"] is None
