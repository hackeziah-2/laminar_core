"""Repository tests for notifications."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationListStatusFilter, NotificationSeverity, NotificationStatus, NotificationType
from app.repository import notification as notification_repo
from app.schemas.notification_schema import NotificationCreate
from tests.factories.notification import seed_notification
from tests.factories.rbac import seed_account, seed_role


@pytest.mark.asyncio
async def test_create_notification_persists_row(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    row = await notification_repo.create_notification(
        db_session,
        NotificationCreate(
            recipient_account_id=recipient_id,
            sender_initials="AK",
            title="ATL Submitted",
            message="ATL awaiting approval",
            module_name="ATL",
            type=NotificationType.APPROVAL,
            severity=NotificationSeverity.INFO,
        ),
    )

    assert row.id is not None
    assert row.uuid is not None
    assert row.status == NotificationStatus.UNREAD
    assert row.sender_initials == "AK"


@pytest.mark.asyncio
async def test_list_notifications_excludes_archived(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    active = await seed_notification(db_session, recipient_account_id=recipient_id, title="Active")
    archived = await seed_notification(db_session, recipient_account_id=recipient_id, title="Archived")
    await notification_repo.archive_notification(db_session, archived)

    items, total = await notification_repo.list_notifications_for_recipient(
        db_session,
        recipient_account_id=recipient_id,
        status_filter=NotificationListStatusFilter.ALL,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].id == active.id


@pytest.mark.asyncio
async def test_list_notifications_filter_unread_and_read(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    unread = await seed_notification(db_session, recipient_account_id=recipient_id, title="Unread")
    read_row = await seed_notification(db_session, recipient_account_id=recipient_id, title="Read")
    await notification_repo.mark_notification_read(db_session, read_row)

    unread_items, unread_total = await notification_repo.list_notifications_for_recipient(
        db_session,
        recipient_account_id=recipient_id,
        status_filter=NotificationListStatusFilter.UNREAD,
        limit=20,
        offset=0,
    )
    read_items, read_total = await notification_repo.list_notifications_for_recipient(
        db_session,
        recipient_account_id=recipient_id,
        status_filter=NotificationListStatusFilter.READ,
        limit=20,
        offset=0,
    )

    assert unread_total == 1
    assert unread_items[0].id == unread.id
    assert read_total == 1
    assert read_items[0].id == read_row.id


@pytest.mark.asyncio
async def test_count_unread_excludes_archived(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    archived_unread = await seed_notification(db_session, recipient_account_id=recipient_id, title="Archived unread")
    await notification_repo.archive_notification(db_session, archived_unread)

    count = await notification_repo.count_unread_for_recipient(db_session, recipient_id)
    assert count == 1


@pytest.mark.asyncio
async def test_pagination_limits_results(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    for idx in range(5):
        await seed_notification(db_session, recipient_account_id=recipient_id, title=f"Item {idx}")

    items, total = await notification_repo.list_notifications_for_recipient(
        db_session,
        recipient_account_id=recipient_id,
        limit=2,
        offset=2,
    )

    assert total == 5
    assert len(items) == 2
