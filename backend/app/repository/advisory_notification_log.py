"""Persistence helpers for advisory notification idempotency logs."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advisory_notification_log import AdvisoryNotificationLog


async def get_log_by_idempotency_key(
    session: AsyncSession,
    *,
    idempotency_key: str,
) -> AdvisoryNotificationLog | None:
    result = await session.execute(
        select(AdvisoryNotificationLog).where(
            AdvisoryNotificationLog.idempotency_key == idempotency_key
        )
    )
    return result.scalars().one_or_none()


def build_advisory_idempotency_key(
    *,
    regulatory_compliance: str,
    advisory_id: int,
    expiry_date: date,
) -> str:
    return (
        f"advisory:{regulatory_compliance}:{advisory_id}:{expiry_date.isoformat()}:"
        "remaining_30_days"
    )
