"""Celery tasks for advisory notifications."""

from __future__ import annotations

import asyncio
import logging

from app.database import AsyncSessionLocal, engine
from app.services.advisory_notification_service import (
    run_remaining_30_days_advisory_notifications,
)
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.advisory_notifications.send_advisory_remaining_30_days_notifications")
def send_advisory_remaining_30_days_notifications() -> dict:
    async def _run() -> dict:
        try:
            async with AsyncSessionLocal() as session:
                return await run_remaining_30_days_advisory_notifications(session)
        finally:
            await engine.dispose()

    result = asyncio.run(_run())
    logger.info("Advisory reminder task result=%s", result)
    return result
