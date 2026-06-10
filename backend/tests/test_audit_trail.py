"""Tests for the reusable audit trail system."""

import json

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.constants.audit import AIRCRAFT_MODULE_NAME, AIRCRAFT_TABLE_NAME
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.repository.audit_log import enrich_audit_log_reads, list_audit_logs
from app.services.audit_trail_service import create_audit_log, detect_changed_fields
from tests.factories.rbac import seed_account, seed_role


class _FakeClient:
    host = "192.168.1.10"


class _FakeRequest(Request):
    def __init__(self) -> None:
        super().__init__(
            {
                "type": "http",
                "headers": Headers(
                    {
                        "user-agent": "pytest-agent/1.0",
                        "x-forwarded-for": "203.0.113.5, 10.0.0.1",
                    }
                ).raw,
                "client": _FakeClient(),
            }
        )


async def _seed_account(session: AsyncSession) -> AccountInformation:
    role_id = await seed_role(session)
    account_id = await seed_account(session, role_id=role_id)
    result = await session.execute(
        select(AccountInformation).where(AccountInformation.id == account_id)
    )
    account = result.scalar_one()
    await session.commit()
    return account


@pytest.mark.asyncio
async def test_create_audit_log(db_session: AsyncSession):
    account = await _seed_account(db_session)
    request = _FakeRequest()

    audit_log = await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=101,
        action=AuditAction.CREATE,
        old_data=None,
        new_data={"registration": "RP-C101", "model": "C172"},
        current_user=account,
        request=request,
    )

    assert audit_log.id is not None
    assert audit_log.module_name == AIRCRAFT_MODULE_NAME
    assert audit_log.table_name == AIRCRAFT_TABLE_NAME
    assert audit_log.record_id == 101
    assert audit_log.action == AuditAction.CREATE.value
    assert audit_log.old_data is None
    assert audit_log.new_data["registration"] == "RP-C101"
    assert audit_log.performed_by_user_id == account.id
    assert audit_log.performed_by_name == account.full_name
    assert audit_log.ip_address == "203.0.113.5"
    assert audit_log.user_agent == "pytest-agent/1.0"
    assert audit_log.changed_fields is None


@pytest.mark.asyncio
async def test_update_audit_log_with_changed_fields(db_session: AsyncSession):
    account = await _seed_account(db_session)
    old_data = {"registration": "RP-C101", "base": "Manila", "status": "Active"}
    new_data = {"registration": "RP-C101", "base": "Cebu", "status": "Maintenance"}

    audit_log = await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=55,
        action=AuditAction.UPDATE,
        old_data=old_data,
        new_data=new_data,
        current_user=account,
        request=None,
    )

    assert audit_log.action == AuditAction.UPDATE.value
    assert audit_log.old_data == old_data
    assert audit_log.new_data == new_data
    assert audit_log.changed_fields == ["base", "status"]
    assert detect_changed_fields(old_data, new_data) == ["base", "status"]


@pytest.mark.asyncio
async def test_delete_audit_log(db_session: AsyncSession):
    account = await _seed_account(db_session)
    old_data = {"id": 77, "registration": "RP-C777", "is_deleted": False}

    audit_log = await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=77,
        action=AuditAction.DELETE,
        old_data=old_data,
        new_data=None,
        current_user=account,
        request=None,
    )

    assert audit_log.action == AuditAction.DELETE.value
    assert audit_log.old_data == old_data
    assert audit_log.new_data is None
    assert audit_log.changed_fields is None


@pytest.mark.asyncio
async def test_audit_log_resolves_created_by_updated_by_to_full_name(
    db_session: AsyncSession,
):
    """Audit log API should expose created_by/updated_by as account full_name."""
    role_id = await seed_role(db_session)
    creator_id = await seed_account(
        db_session,
        role_id=role_id,
        username="kevin_audit_user",
    )
    updater_id = await seed_account(
        db_session,
        role_id=role_id,
        username="vivien_audit_user",
    )
    creator_result = await db_session.execute(
        select(AccountInformation).where(AccountInformation.id == creator_id)
    )
    updater_result = await db_session.execute(
        select(AccountInformation).where(AccountInformation.id == updater_id)
    )
    creator = creator_result.scalar_one()
    updater = updater_result.scalar_one()
    creator.first_name = "Kevin Paul"
    creator.last_name = "Lamadrid"
    updater.first_name = "Vivien"
    updater.last_name = "Lamadrid"
    await db_session.flush()

    await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=501,
        action=AuditAction.UPDATE,
        old_data={"registration": "RP-C501", "created_by": creator_id, "updated_by": creator_id},
        new_data={"registration": "RP-C502", "created_by": creator_id, "updated_by": updater_id},
        current_user=updater,
        request=None,
    )

    items, _ = await list_audit_logs(
        db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        record_id=501,
    )
    assert len(items) == 1
    assert items[0].old_data["created_by"] == "Kevin Paul Lamadrid"
    assert items[0].old_data["updated_by"] == "Kevin Paul Lamadrid"
    assert items[0].new_data["created_by"] == "Kevin Paul Lamadrid"
    assert items[0].new_data["updated_by"] == "Vivien Lamadrid"


@pytest.mark.asyncio
async def test_enrich_audit_log_reads_handles_empty_items(db_session: AsyncSession):
    assert await enrich_audit_log_reads(db_session, []) == []


@pytest.mark.asyncio
async def test_filter_audit_logs_by_module_name(db_session: AsyncSession):
    account = await _seed_account(db_session)

    await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=1,
        action=AuditAction.CREATE,
        old_data=None,
        new_data={"registration": "RP-C001"},
        current_user=account,
        request=None,
    )
    await create_audit_log(
        db=db_session,
        module_name="accounts",
        table_name="account_information",
        record_id=2,
        action=AuditAction.UPDATE,
        old_data={"status": True},
        new_data={"status": False},
        current_user=account,
        request=None,
    )

    items, total = await list_audit_logs(
        db_session,
        limit=10,
        offset=0,
        module_name=AIRCRAFT_MODULE_NAME,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].module_name == AIRCRAFT_MODULE_NAME


@pytest.mark.asyncio
async def test_filter_audit_logs_by_performed_by_user_id(db_session: AsyncSession):
    account = await _seed_account(db_session)
    role_id = await seed_role(db_session)
    other_account_id = await seed_account(db_session, role_id=role_id, username="other_user")
    await db_session.commit()

    await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=10,
        action=AuditAction.CREATE,
        old_data=None,
        new_data={"registration": "RP-C010"},
        current_user=account,
        request=None,
    )
    await create_audit_log(
        db=db_session,
        module_name=AIRCRAFT_MODULE_NAME,
        table_name=AIRCRAFT_TABLE_NAME,
        record_id=11,
        action=AuditAction.CREATE,
        old_data=None,
        new_data={"registration": "RP-C011"},
        current_user=await db_session.get(AccountInformation, other_account_id),
        request=None,
    )

    items, total = await list_audit_logs(
        db_session,
        limit=10,
        offset=0,
        performed_by_user_id=account.id,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].performed_by_user_id == account.id


@pytest.mark.asyncio
async def test_audit_logs_pagination(db_session: AsyncSession):
    account = await _seed_account(db_session)

    for record_id in range(1, 6):
        await create_audit_log(
            db=db_session,
            module_name=AIRCRAFT_MODULE_NAME,
            table_name=AIRCRAFT_TABLE_NAME,
            record_id=record_id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data={"registration": f"RP-C{record_id:03d}"},
            current_user=account,
            request=None,
        )

    page_1, total = await list_audit_logs(db_session, limit=2, offset=0)
    page_2, _ = await list_audit_logs(db_session, limit=2, offset=2)

    assert total == 5
    assert len(page_1) == 2
    assert len(page_2) == 2
    assert page_1[0].id != page_2[0].id


def test_aircraft_create_writes_audit_log(client: TestClient, test_aircraft_data: dict):
    """Aircraft create endpoint should persist a CREATE audit log after commit."""
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert response.status_code == 200
    aircraft_id = response.json()["id"]

    audit_response = client.get(
        f"/api/v1/audit-logs/?module_name={AIRCRAFT_MODULE_NAME}&record_id={aircraft_id}"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    create_logs = [item for item in payload["items"] if item["action"] == "CREATE"]
    assert len(create_logs) == 1
    assert create_logs[0]["new_data"]["registration"] == test_aircraft_data["registration"]
    assert create_logs[0]["old_data"] is None


def test_audit_log_detail_endpoint(client: TestClient, test_aircraft_data: dict):
    """Audit log detail endpoint returns a single record."""
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert response.status_code == 200
    aircraft_id = response.json()["id"]

    list_response = client.get(
        f"/api/v1/audit-logs/?module_name={AIRCRAFT_MODULE_NAME}&record_id={aircraft_id}"
    )
    assert list_response.status_code == 200
    audit_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/api/v1/audit-logs/{audit_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == audit_id
    assert detail["module_name"] == AIRCRAFT_MODULE_NAME
    assert detail["action"] == "CREATE"


def test_audit_logs_api_summary_counts(client: TestClient, test_aircraft_data: dict):
    """Audit logs list response includes summary counts."""
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(test_aircraft_data)},
        files={},
    )
    assert response.status_code == 200

    list_response = client.get("/api/v1/audit-logs/?limit=10&page=1")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert "summary" in payload
    assert payload["summary"]["total"] >= 1
    assert payload["summary"]["creates"] >= 1


def test_audit_logs_api_pagination_response(client: TestClient, test_aircraft_data: dict):
    """Audit logs API returns page, limit, total, and items."""
    for idx in range(3):
        payload = {**test_aircraft_data, "msn": f"TEST-MSN-AUDIT-{idx}", "registration": f"TEST-AUDIT-{idx}"}
        response = client.post(
            "/api/v1/aircraft/",
            data={"json_data": json.dumps(payload)},
            files={},
        )
        assert response.status_code == 200

    response = client.get("/api/v1/audit-logs/?limit=2&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 2
    assert data["total"] >= 3
    assert len(data["items"]) == 2
    assert "items" in data
