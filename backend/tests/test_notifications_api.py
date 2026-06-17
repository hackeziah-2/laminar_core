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
    assert response.json() == {"unread_count": 2}


@pytest.mark.asyncio
async def test_mark_one_notification_read(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=1)
    notification_id = (
        await async_authenticated_client.get("/api/v1/notifications?status=unread")
    ).json()["items"][0]["id"]

    response = await async_authenticated_client.patch(f"/api/v1/notifications/{notification_id}/read")
    assert response.status_code == 200
    assert response.json()["status"] == "READ"


@pytest.mark.asyncio
async def test_mark_all_notifications_read(async_authenticated_client: AsyncClient, auth_account_id: int):
    await _seed_recipient_notifications(auth_account_id, count=2)

    response = await async_authenticated_client.patch("/api/v1/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["updated_count"] == 2

    unread = await async_authenticated_client.get("/api/v1/notifications/unread-count")
    assert unread.json()["unread_count"] == 0


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
    await _seed_recipient_notifications(auth_account_id, count=3)

    response = await async_authenticated_client.patch("/api/v1/notifications/clear-all")
    assert response.status_code == 200
    assert response.json()["archived_count"] == 3

    listed = await async_authenticated_client.get("/api/v1/notifications?status=all")
    assert listed.json()["total"] == 0


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
