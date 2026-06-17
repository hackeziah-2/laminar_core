"""WebSocket tests for realtime notifications."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.websocket.notification_manager import NotificationConnectionManager


def test_websocket_connection_success(client: TestClient, auth_account_id: int):
    token = create_access_token({"sub": str(auth_account_id), "username": "ws-user"})
    with client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as websocket:
        websocket.send_text("ping")


def test_websocket_rejects_missing_token(client: TestClient):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/notifications/ws"):
            pass


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
