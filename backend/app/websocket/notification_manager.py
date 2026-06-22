"""WebSocket connection manager for realtime notification delivery."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationConnectionManager:
    """Track active WebSocket connections per account and push events."""

    def __init__(self) -> None:
        self._connections: DefaultDict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, account_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[account_id].add(websocket)
        logger.debug("WebSocket connected for account_id=%s", account_id)

    async def disconnect(self, account_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(account_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(account_id, None)
        logger.debug("WebSocket disconnected for account_id=%s", account_id)

    async def send_to_user(self, account_id: int, payload: Dict[str, Any]) -> None:
        """Push a JSON payload to all active connections for the account."""
        async with self._lock:
            sockets: List[WebSocket] = list(self._connections.get(account_id, set()))

        stale: List[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
                logger.warning(
                    "Failed to push notification event to account_id=%s",
                    account_id,
                    exc_info=True,
                )

        if stale:
            async with self._lock:
                active = self._connections.get(account_id)
                if active:
                    for websocket in stale:
                        active.discard(websocket)
                    if not active:
                        self._connections.pop(account_id, None)

    def active_connection_count(self, account_id: int) -> int:
        return len(self._connections.get(account_id, set()))


_notification_manager = NotificationConnectionManager()


def get_notification_manager() -> NotificationConnectionManager:
    """Return the process-wide notification WebSocket manager."""
    return _notification_manager
