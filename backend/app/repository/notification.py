"""Data access layer for notifications."""

from __future__ import annotations

from math import ceil
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import ph_now
from app.enums.notification import NotificationListStatusFilter, NotificationStatus
from app.models.notification import Notification
from app.schemas.notification_schema import NotificationCreate


async def create_notification(
    session: AsyncSession,
    data: NotificationCreate,
) -> Notification:
    """Persist a new notification row."""
    row = Notification(
        recipient_account_id=data.recipient_account_id,
        sender_account_id=data.sender_account_id,
        sender_initials=data.sender_initials.strip().upper()[:5],
        title=data.title.strip(),
        message=data.message.strip(),
        module_name=data.module_name.strip(),
        type=data.type,
        severity=data.severity,
        status=NotificationStatus.UNREAD,
        reference_id=data.reference_id,
        reference_type=data.reference_type,
        notification_metadata=data.metadata,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_notification_for_recipient(
    session: AsyncSession,
    notification_id: int,
    recipient_account_id: int,
) -> Optional[Notification]:
    """Fetch a notification scoped to the recipient."""
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_account_id == recipient_account_id,
        )
    )
    return result.scalar_one_or_none()


async def list_notifications_for_recipient(
    session: AsyncSession,
    *,
    recipient_account_id: int,
    status_filter: NotificationListStatusFilter = NotificationListStatusFilter.ALL,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Notification], int]:
    """List notifications for a recipient, excluding archived rows."""
    filters = [Notification.recipient_account_id == recipient_account_id]
    filters.append(Notification.status != NotificationStatus.ARCHIVED)
    if status_filter == NotificationListStatusFilter.UNREAD:
        filters.append(Notification.status == NotificationStatus.UNREAD)
    elif status_filter == NotificationListStatusFilter.READ:
        filters.append(Notification.status == NotificationStatus.READ)

    count_stmt = select(func.count()).select_from(Notification).where(*filters)
    total = int((await session.execute(count_stmt)).scalar() or 0)

    stmt = (
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def count_unread_for_recipient(
    session: AsyncSession,
    recipient_account_id: int,
) -> int:
    """Count unread, non-archived notifications for a recipient."""
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_account_id == recipient_account_id,
            Notification.status == NotificationStatus.UNREAD,
        )
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def mark_notification_read(
    session: AsyncSession,
    notification: Notification,
) -> Notification:
    """Mark a single notification as read."""
    if notification.status != NotificationStatus.UNREAD:
        return notification
    notification.mark_read()
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def mark_all_notifications_read(
    session: AsyncSession,
    recipient_account_id: int,
) -> int:
    """Mark all unread notifications as read for a recipient."""
    now = ph_now()
    result = await session.execute(
        update(Notification)
        .where(
            Notification.recipient_account_id == recipient_account_id,
            Notification.status == NotificationStatus.UNREAD,
        )
        .values(
            status=NotificationStatus.READ,
            read_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return int(result.rowcount or 0)


async def archive_notification(
    session: AsyncSession,
    notification: Notification,
) -> Notification:
    """Archive a single notification."""
    if notification.status == NotificationStatus.ARCHIVED:
        return notification
    notification.mark_archived()
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def archive_all_notifications(
    session: AsyncSession,
    recipient_account_id: int,
) -> int:
    """Soft-archive all non-archived notifications for a recipient."""
    now = ph_now()
    result = await session.execute(
        update(Notification)
        .where(
            Notification.recipient_account_id == recipient_account_id,
            Notification.status != NotificationStatus.ARCHIVED,
        )
        .values(
            status=NotificationStatus.ARCHIVED,
            archived_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return int(result.rowcount or 0)


def compute_total_pages(total: int, limit: int) -> int:
    """Compute total pages for pagination."""
    if total <= 0:
        return 0
    return ceil(total / limit)
