"""Event-driven notification publishing helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationSeverity, NotificationType
from app.models.account import AccountInformation
from app.schemas.notification_schema import NotificationCreate, NotificationRead
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def derive_sender_initials(
    account: Optional[AccountInformation],
    *,
    fallback: str = "SYS",
) -> str:
    """Build sender initials from an account's name."""
    if account is None:
        return fallback[:5]
    first = (account.first_name or "").strip()
    last = (account.last_name or "").strip()
    if first and last:
        return f"{first[0]}{last[0]}".upper()[:5]
    if first:
        return first[:2].upper()
    if last:
        return last[:2].upper()
    username = (account.username or "").strip()
    return (username[:2] or fallback).upper()[:5]


async def publish_notification_event(
    session: AsyncSession,
    *,
    recipient_account_id: int,
    title: str,
    message: str,
    module_name: str,
    notification_type: NotificationType,
    severity: NotificationSeverity = NotificationSeverity.INFO,
    sender_account: Optional[AccountInformation] = None,
    sender_initials: Optional[str] = None,
    reference_id: Optional[int] = None,
    reference_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    push_realtime: bool = True,
) -> NotificationRead:
    """
    Publish a notification from a business module without coupling to transport details.

    Example flow: ATL approved -> publish_notification_event -> DB + WebSocket.
    """
    initials = sender_initials or derive_sender_initials(sender_account)
    service = NotificationService(session)
    notification = await service.create_notification(
        NotificationCreate(
            recipient_account_id=recipient_account_id,
            sender_account_id=sender_account.id if sender_account else None,
            sender_initials=initials,
            title=title,
            message=message,
            module_name=module_name,
            type=notification_type,
            severity=severity,
            reference_id=reference_id,
            reference_type=reference_type,
            metadata=metadata,
        ),
        push_realtime=push_realtime,
    )
    logger.info(
        "Notification published id=%s recipient=%s module=%s",
        notification.id,
        recipient_account_id,
        module_name,
    )
    return notification
