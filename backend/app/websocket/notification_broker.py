"""Redis pub/sub bridge for cross-process WebSocket notification delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from app.websocket.notification_manager import NotificationConnectionManager, get_notification_manager

logger = logging.getLogger(__name__)

NOTIFICATION_REALTIME_CHANNEL = "notifications:realtime"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

_subscriber_task: Optional[asyncio.Task] = None


async def publish_notification_realtime(account_id: int, payload: Dict[str, Any]) -> None:
    """Publish a realtime notification event to all API worker processes."""
    origin_pid = os.getpid()
    message = json.dumps(
        {"account_id": account_id, "payload": payload, "origin_pid": origin_pid}
    )
    manager = get_notification_manager()
    await manager.send_to_user(account_id, payload)
    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            receivers = await client.publish(NOTIFICATION_REALTIME_CHANNEL, message)
            logger.info(
                "[notifications-ws] redis publish event=%s account_id=%s receivers=%s pid=%s",
                payload.get("event"),
                account_id,
                receivers,
                origin_pid,
            )
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "Redis notification publish failed; local WebSocket push already attempted",
            exc_info=True,
        )


async def _subscriber_loop(manager: NotificationConnectionManager) -> None:
    while True:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(NOTIFICATION_REALTIME_CHANNEL)
            logger.info(
                "[notifications-ws] subscriber connected channel=%s pid=%s",
                NOTIFICATION_REALTIME_CHANNEL,
                os.getpid(),
            )
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = json.loads(message["data"])
                message_origin_pid = data.get("origin_pid")
                if message_origin_pid is not None and int(message_origin_pid) == os.getpid():
                    continue
                account_id = int(data["account_id"])
                payload = data["payload"]
                await manager.send_to_user(account_id, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification subscriber error; reconnecting in 2s")
            await asyncio.sleep(2)
        finally:
            try:
                await pubsub.unsubscribe(NOTIFICATION_REALTIME_CHANNEL)
                await pubsub.aclose()
            except Exception:
                pass
            await client.aclose()


def start_notification_subscriber() -> None:
    """Start background Redis subscriber for the current API worker process."""
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        return
    manager = get_notification_manager()
    _subscriber_task = asyncio.create_task(_subscriber_loop(manager))
    logger.info("[notifications-ws] subscriber task scheduled pid=%s", os.getpid())
