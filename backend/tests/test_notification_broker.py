"""Tests for Redis notification broker and local fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.websocket.notification_broker import publish_notification_realtime
from app.websocket.notification_manager import get_notification_manager


@pytest.mark.asyncio
async def test_publish_uses_local_fallback_when_redis_unavailable(monkeypatch):
    manager = get_notification_manager()

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    socket = _FakeWebSocket()
    account_id = 4242
    manager._connections[account_id].add(socket)

    def _raise_redis_error(*_args, **_kwargs):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(
        "app.websocket.notification_broker.aioredis.from_url",
        _raise_redis_error,
    )

    payload = {"event": "new_notification", "data": {"id": 1, "title": "Test"}}
    await publish_notification_realtime(account_id, payload)

    assert len(socket.messages) == 1
    assert socket.messages[0]["event"] == "new_notification"
    manager._connections[account_id].discard(socket)


@pytest.mark.asyncio
async def test_publish_falls_back_when_no_subscribers(monkeypatch):
    manager = get_notification_manager()

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    socket = _FakeWebSocket()
    account_id = 5151
    manager._connections[account_id].add(socket)

    mock_client = MagicMock()
    mock_client.publish = AsyncMock(return_value=0)
    mock_client.aclose = AsyncMock()

    monkeypatch.setattr(
        "app.websocket.notification_broker.aioredis.from_url",
        lambda *_args, **_kwargs: mock_client,
    )

    payload = {"event": "unread_count_updated", "data": {"unread_count": 2}}
    await publish_notification_realtime(account_id, payload)

    assert len(socket.messages) == 1
    assert socket.messages[0]["data"]["unread_count"] == 2
    manager._connections[account_id].discard(socket)
