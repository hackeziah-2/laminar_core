"""Advisory notification event publisher."""

from __future__ import annotations

import logging
from typing import List, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationSeverity, NotificationType
from app.events.notification_events import publish_notification_event
from app.repository.user_repository import get_active_accounts_by_roles

logger = logging.getLogger(__name__)


async def publish_advisory_notification_event(
    session: AsyncSession,
    *,
    title: str,
    message: str,
    module_name: str,
    recipients_role_names: Sequence[str],
    metadata: dict,
    reference_id: int | None = None,
) -> int:
    role_accounts = await get_active_accounts_by_roles(session, recipients_role_names)
    recipient_ids = sorted({account.id for account in role_accounts})
    published = 0
    for recipient_id in recipient_ids:
        await publish_notification_event(
            session,
            recipient_account_id=recipient_id,
            title=title,
            message=message,
            module_name=module_name,
            notification_type=NotificationType.REMINDER,
            severity=NotificationSeverity.WARNING,
            reference_id=reference_id,
            reference_type="ADVISORY",
            metadata=metadata,
        )
        published += 1
    logger.info(
        "Advisory event published module=%s recipients=%s",
        module_name,
        published,
    )
    return published
