"""Seed notification rows for tests."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationSeverity, NotificationStatus, NotificationType
from app.models.notification import Notification
from app.schemas.notification_schema import NotificationCreate
from app.repository.notification import create_notification


async def seed_notification(
    session: AsyncSession,
    *,
    recipient_account_id: int,
    sender_account_id: Optional[int] = None,
    sender_initials: str = "TU",
    title: str = "Test notification",
    message: str = "Test message body",
    module_name: str = "ATL",
    notification_type: NotificationType = NotificationType.INFO,
    severity: NotificationSeverity = NotificationSeverity.INFO,
    status: Optional[NotificationStatus] = None,
    reference_id: Optional[int] = None,
    reference_type: Optional[str] = None,
) -> Notification:
    row = await create_notification(
        session,
        NotificationCreate(
            recipient_account_id=recipient_account_id,
            sender_account_id=sender_account_id,
            sender_initials=sender_initials,
            title=title,
            message=message,
            module_name=module_name,
            type=notification_type,
            severity=severity,
            reference_id=reference_id,
            reference_type=reference_type,
        ),
    )
    if status is not None and status != NotificationStatus.UNREAD:
        row.status = status
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row
