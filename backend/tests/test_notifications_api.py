"""API integration tests for notifications."""

import pytest
from httpx import AsyncClient

from tests.factories.notification import seed_notification
from tests.factories.rbac import seed_account, seed_role


async def _seed_recipient_notifications(account_id: int, count: int = 2) -> None:
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        for idx in range(count):
            await seed_notification(
                session,
                recipient_account_id=account_id,
                title=f"Notification {idx + 1}",
            )
        await session.commit()


@pytest.mark.asyncio
async def test_list_all_notifications(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=2)

    response = await async_authenticated_client.get("/api/v1/notifications?status=all")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["unread_count"] == 2
    assert "uuid" in payload["items"][0]
    assert "time_ago" in payload["items"][0]


@pytest.mark.asyncio
async def test_list_unread_notifications(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)

    response = await async_authenticated_client.get("/api/v1/notifications?status=unread")
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_read_notifications(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)
    items = (await async_authenticated_client.get("/api/v1/notifications?status=unread")).json()["items"]
    notification_id = items[0]["id"]

    await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/read")

    response = await async_authenticated_client.get("/api/v1/notifications?status=read")
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_unread_count_endpoint(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=2)

    response = await async_authenticated_client.get("/api/v1/notifications/unread-count")
    assert response.status_code == 200
    assert response.json() == {"unread_count": 2, "total": 2, "read_count": 0}


@pytest.mark.asyncio
async def test_unread_count_uses_recipient_account(
    async_authenticated_client: AsyncClient,
    auth_account_id: int,
):
    await _seed_recipient_notifications(auth_account_id, count=2)

    response = await async_authenticated_client.get(
        f"/api/v1/notifications/unread-count?recipient_account={auth_account_id}"
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"unread_count": 2, "total": 2, "read_count": 0}


@pytest.mark.asyncio
async def test_mark_one_notification_read(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)
    notification_id = (
        await async_authenticated_client.get("/api/v1/notifications?status=unread")
    ).json()["items"][0]["id"]

    response = await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/read")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READ"
    assert body["notice"] == "Notification marked as read."
    assert body["unread_count"] == 0
    assert body["read_count"] == 1
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_mark_all_notifications_read(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=2)

    response = await async_authenticated_client.patch("/api/v1/notifications/read-all")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "All notifications marked as read."
    assert body["updated_count"] == 2
    assert body["unread_count"] == 0
    assert body["read_count"] == 2
    assert body["total"] == 2

    unread = await async_authenticated_client.get("/api/v1/notifications/unread-count")
    assert unread.json()["unread_count"] == 0
    listed = await async_authenticated_client.get("/api/v1/notifications?status=all")
    body = listed.json()
    assert body["total"] == 2
    assert body["inbox_total"] == 2
    assert body["unread_count"] == 0
    assert body["read_count"] == 2
    assert [item["status"] for item in body["items"]] == ["READ", "READ"]


@pytest.mark.asyncio
async def test_mark_one_notification_unread(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)
    notification_id = (
        await async_authenticated_client.get("/api/v1/notifications?status=unread")
    ).json()["items"][0]["id"]

    await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/read")
    response = await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/unread")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "UNREAD"
    assert body["read_at"] is None
    assert body["notice"] == "Notification marked as unread."
    assert body["unread_count"] == 1
    assert body["total"] == 1

    unread = await async_authenticated_client.get("/api/v1/notifications/unread-count")
    listed = await async_authenticated_client.get("/api/v1/notifications?status=unread")
    assert unread.json()["unread_count"] == 1
    assert listed.json()["total"] == 1


@pytest.mark.asyncio
async def test_archive_one_notification(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)
    notification_id = (
        await async_authenticated_client.get("/api/v1/notifications?status=unread")
    ).json()["items"][0]["id"]

    response = await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/archive")
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"

    listed = await async_authenticated_client.get("/api/v1/notifications?status=all")
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_clear_all_notifications(async_authenticated_client: AsyncClient, auth_account_id: int):
    from sqlalchemy import func, select

    from app.enums.notification import NotificationStatus
    from app.models.notification import Notification
    from tests.conftest import TestSessionLocal

    await _seed_recipient_notifications(auth_account_id, count=3)
    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()
        await seed_notification(
            session,
            recipient_account_id=auth_account_id,
            title="Already archived",
            status=NotificationStatus.ARCHIVED,
        )
        await seed_notification(session, recipient_account_id=other_account_id, title="Other user")
        await session.commit()

    response = await async_authenticated_client.patch("/api/v1/notifications/clear-all")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "All notifications deleted."
    assert body["deleted_count"] == 4
    assert body["unread_count"] == 0
    assert body["read_count"] == 0
    assert body["total"] == 0

    listed = await async_authenticated_client.get("/api/v1/notifications?status=all")
    assert listed.json()["total"] == 0
    assert listed.json()["inbox_total"] == 0
    assert listed.json()["unread_count"] == 0
    assert listed.json()["read_count"] == 0
    read_list = await async_authenticated_client.get("/api/v1/notifications?status=read")
    assert read_list.json()["total"] == 0

    async with TestSessionLocal() as session:
        owner_stored = await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_account_id == auth_account_id)
        )
        other_stored = await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_account_id == other_account_id)
        )
    assert owner_stored == 0
    assert other_stored == 1


@pytest.mark.asyncio
async def test_delete_one_notification_updates_counts(
    async_authenticated_client: AsyncClient,
    auth_account_id: int,
):
    from tests.conftest import TestSessionLocal

    await _seed_recipient_notifications(auth_account_id, count=2)
    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()
        await seed_notification(session, recipient_account_id=other_account_id, title="Other user")
        await session.commit()

    items = (await async_authenticated_client.get("/api/v1/notifications?status=all")).json()["items"]
    notification_id = items[0]["id"]

    response = await async_authenticated_client.delete(
        f"/api/v1/notifications/{notification_id}"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Notification deleted."
    assert body["deleted_count"] == 1
    assert body["total"] == 1
    assert body["unread_count"] == 1

    listed = await async_authenticated_client.get("/api/v1/notifications?status=all")
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert listed_body["inbox_total"] == 1
    assert listed_body["unread_count"] == 1
    assert all(item["id"] != notification_id for item in listed_body["items"])

    missing = await async_authenticated_client.delete(
        f"/api/v1/notifications/{notification_id}"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Notification not found."


@pytest.mark.asyncio
async def test_pagination(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=5)

    response = await async_authenticated_client.get("/api/v1/notifications?status=all&page=2&limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["limit"] == 2
    assert payload["total"] == 5
    assert payload["total_pages"] == 3
    assert len(payload["items"]) == 2


@pytest.mark.asyncio
async def test_invalid_status_returns_validation_error(async_client: AsyncClient, async_auth_headers: dict):
    response = await async_client.get(
        "/api/v1/notifications?status=invalid",
        headers=async_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.no_auth
@pytest.mark.asyncio
async def test_unauthorized_returns_401(async_client: AsyncClient):
    response = await async_client.get("/api/v1/notifications")
    assert response.status_code == 401
