"""Permission and ownership tests for notifications."""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from tests.factories.notification import seed_notification
from tests.factories.rbac import seed_account, seed_role


async def _seed_other_user_notification(owner_account_id: int) -> int:
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        row = await seed_notification(session, recipient_account_id=owner_account_id, title="Private")
        await session.commit()
        return row.id


@pytest.mark.asyncio
async def test_user_cannot_mark_another_users_notification(
    async_client: AsyncClient,
    auth_account_id: int,
    async_auth_headers: dict,
):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()

    notification_id = await _seed_other_user_notification(other_account_id)

    response = await async_client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=async_auth_headers,
    )
    assert response.status_code == 404

    unread_response = await async_client.patch(
        f"/api/v1/notifications/{notification_id}/unread",
        headers=async_auth_headers,
    )
    assert unread_response.status_code == 404

    delete_response = await async_client.delete(
        f"/api/v1/notifications/{notification_id}",
        headers=async_auth_headers,
    )
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Notification not found."


@pytest.mark.asyncio
async def test_bulk_actions_reject_another_recipient(
    async_client: AsyncClient,
    auth_account_id: int,
    async_auth_headers: dict,
):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()

    await _seed_other_user_notification(other_account_id)
    await _seed_other_user_notification(auth_account_id)

    for path in ("/api/v1/notifications/read-all", "/api/v1/notifications/clear-all"):
        response = await async_client.patch(
            f"{path}?recipient_account={other_account_id}",
            headers=async_auth_headers,
        )
        assert response.status_code == 403, response.text

    own = await async_client.get("/api/v1/notifications?status=all", headers=async_auth_headers)
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert own.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_unread_count_rejects_another_recipient(
    async_client: AsyncClient,
    auth_account_id: int,
    async_auth_headers: dict,
):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()

    await _seed_other_user_notification(other_account_id)

    response = await async_client.get(
        f"/api/v1/notifications/unread-count?recipient_account={other_account_id}",
        headers=async_auth_headers,
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_user_only_sees_own_notifications(async_client: AsyncClient, auth_account_id: int):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        role_id = await seed_role(session)
        other_account_id = await seed_account(session, role_id=role_id)
        await session.commit()

    await _seed_other_user_notification(other_account_id)
    await _seed_other_user_notification(auth_account_id)

    token = create_access_token({"sub": str(auth_account_id), "username": "owner"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/api/v1/notifications?status=all", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
