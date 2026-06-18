"""WebSocket tests for realtime notifications."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.enums.notification import NotificationSeverity, NotificationType
from app.schemas.notification_schema import NotificationCreate
from app.services.notification_service import NotificationService
from app.websocket.notification_manager import NotificationConnectionManager, get_notification_manager


def test_websocket_connection_success(client: TestClient, auth_account_id: int):
    token = create_access_token({"sub": str(auth_account_id), "username": "ws-user"})
    with client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as websocket:
        websocket.send_text("ping")


def test_websocket_rejects_missing_token(client: TestClient):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/notifications/ws"):
            pass


@pytest.mark.asyncio
async def test_service_realtime_push_reaches_connected_socket(
    db_session: AsyncSession,
    auth_account_id: int,
):
    """Verify create_notification delivers to an active in-process WebSocket connection."""
    manager = get_notification_manager()

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    socket = _FakeWebSocket()
    manager._connections[auth_account_id].add(socket)

    service = NotificationService(db_session)
    created = await service.create_notification(
        NotificationCreate(
            recipient_account_id=auth_account_id,
            sender_initials="TU",
            title="Realtime test",
            message="Push via local delivery",
            module_name="advisory",
            type=NotificationType.REMINDER,
            severity=NotificationSeverity.WARNING,
        ),
        push_realtime=True,
    )

    assert created.title == "Realtime test"
    assert len(socket.messages) == 1
    assert socket.messages[0]["event"] == "new_notification"
    assert socket.messages[0]["data"]["id"] == created.id

    manager._connections[auth_account_id].discard(socket)


@pytest.mark.asyncio
async def test_manager_push_notification_event():
    manager = NotificationConnectionManager()

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    socket = _FakeWebSocket()
    manager._connections[42].add(socket)

    await manager.send_to_user(
        42,
        {
            "event": "new_notification",
            "data": {"id": 123, "title": "Maintenance reminder", "unread_count": 3},
        },
    )

    assert socket.messages[0]["event"] == "new_notification"
    assert socket.messages[0]["data"]["unread_count"] == 3


@pytest.mark.asyncio
async def test_manager_disconnect_cleanup():
    manager = NotificationConnectionManager()

    class _FakeWebSocket:
        pass

    socket = _FakeWebSocket()
    manager._connections[7].add(socket)
    await manager.disconnect(7, socket)
    assert manager.active_connection_count(7) == 0
