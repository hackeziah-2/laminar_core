"""Service-layer tests for notifications."""

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import (
    NotificationListStatusFilter,
    NotificationSeverity,
    NotificationStatus,
    NotificationType,
)
from app.models.notification import Notification
from app.schemas.notification_schema import NotificationCreate
from app.services.notification_service import NotificationService
from tests.factories.notification import seed_notification
from tests.factories.rbac import seed_account, seed_role


async def _stored_notification_count(session: AsyncSession, recipient_account_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_account_id == recipient_account_id)
    )
    return int(result.scalar_one())


@pytest.mark.asyncio
async def test_create_notification_returns_read_schema(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    service = NotificationService(db_session)
    created = await service.create_notification(
        NotificationCreate(
            recipient_account_id=recipient_id,
            sender_initials="MQ",
            title="Maintenance reminder",
            message="Inspection due soon",
            module_name="Maintenance",
            type=NotificationType.REMINDER,
            severity=NotificationSeverity.WARNING,
        ),
        push_realtime=False,
    )

    assert created.title == "Maintenance reminder"
    assert created.uuid is not None
    assert created.time_ago
    assert created.status.value == "UNREAD"


@pytest.mark.asyncio
async def test_get_notifications_includes_unread_count(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    await seed_notification(db_session, recipient_account_id=recipient_id, title="Second")

    service = NotificationService(db_session)
    page = await service.get_notifications(recipient_id, page=1, limit=20)

    assert page.total == 2
    assert page.unread_count == 2
    assert len(page.items) == 2


@pytest.mark.asyncio
async def test_mark_as_read_updates_status(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    row = await seed_notification(db_session, recipient_account_id=recipient_id)
    service = NotificationService(db_session)
    updated = await service.mark_as_read(row.id, recipient_id)

    assert updated.status.value == "READ"
    assert updated.read_at is not None


@pytest.mark.asyncio
async def test_mark_all_as_read(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    await seed_notification(db_session, recipient_account_id=recipient_id, title="Second")

    service = NotificationService(db_session)
    updated_count = await service.mark_all_as_read(recipient_id)
    unread = await service.get_unread_count(recipient_id)

    assert updated_count == 2
    assert unread.unread_count == 0


def test_normalize_atl_metadata_resolves_aircraft_id_from_nested_aircraft():
    metadata = {
        "sequence_no": "000123",
        "atl_batch_fk": 5,
        "aircraft": {"id": 7, "registration": "RP-C123", "model": "C172"},
        "url": "/atl/99",
    }

    normalized = NotificationService._normalize_metadata(
        reference_type="ATL",
        reference_id=99,
        metadata=metadata,
    )

    assert normalized is not None
    assert normalized["aircraft_id"] == 7
    assert (
        normalized["url"]
        == "/technical-logbook/sequence_no=000123?aircraft_id=7/atl_batch_fk=5"
    )


@pytest.mark.asyncio
async def test_clear_all_deletes_notifications(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    other_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    await seed_notification(
        db_session,
        recipient_account_id=recipient_id,
        title="Archived",
        status=NotificationStatus.ARCHIVED,
    )
    other = await seed_notification(db_session, recipient_account_id=other_id, title="Theirs")

    service = NotificationService(db_session)
    deleted_count = await service.clear_all_notifications(recipient_id)
    page = await service.get_notifications(
        recipient_id,
        status_filter=NotificationListStatusFilter.ALL,
    )

    assert deleted_count == 2
    assert page.total == 0
    assert page.inbox_total == 0
    assert page.unread_count == 0
    assert page.read_count == 0
    assert await _stored_notification_count(db_session, recipient_id) == 0
    assert await _stored_notification_count(db_session, other_id) == 1


@pytest.mark.asyncio
async def test_mark_as_unread_restores_inbox_state(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    row = await seed_notification(db_session, recipient_account_id=recipient_id)
    service = NotificationService(db_session)
    await service.mark_as_read(row.id, recipient_id)
    updated = await service.mark_as_unread(row.id, recipient_id)
    unread = await service.get_unread_count(recipient_id)
    page = await service.get_notifications(
        recipient_id,
        status_filter=NotificationListStatusFilter.UNREAD,
    )

    assert updated.status.value == "UNREAD"
    assert updated.read_at is None
    assert unread.unread_count == 1
    assert page.total == 1
    assert page.inbox_total == 1


@pytest.mark.asyncio
async def test_mark_all_keeps_notifications_and_clear_all_removes_them(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    await seed_notification(db_session, recipient_account_id=recipient_id, title="Second")
    service = NotificationService(db_session)

    updated_count = await service.mark_all_as_read(recipient_id)
    marked = await service.get_notifications(recipient_id)

    assert updated_count == 2
    assert marked.total == 2
    assert marked.inbox_total == 2
    assert marked.unread_count == 0
    assert marked.read_count == 2
    assert [item.status.value for item in marked.items] == ["READ", "READ"]
    assert all(item.archived_at is None for item in marked.items)

    deleted_count = await service.clear_all_notifications(recipient_id)
    cleared = await service.get_notifications(recipient_id)
    read_page = await service.get_notifications(
        recipient_id,
        status_filter=NotificationListStatusFilter.READ,
    )

    assert deleted_count == 2
    assert cleared.total == 0
    assert cleared.inbox_total == 0
    assert cleared.unread_count == 0
    assert cleared.read_count == 0
    assert read_page.total == 0
    assert await _stored_notification_count(db_session, recipient_id) == 0


@pytest.mark.asyncio
async def test_inbox_actions_do_not_change_other_recipients(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    owner_id = await seed_account(db_session, role_id=role_id)
    other_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    own = await seed_notification(db_session, recipient_account_id=owner_id, title="Mine")
    other = await seed_notification(db_session, recipient_account_id=other_id, title="Theirs")
    service = NotificationService(db_session)

    await service.mark_as_read(own.id, owner_id)
    await service.mark_as_unread(own.id, owner_id)
    await service.mark_all_as_read(owner_id)
    await service.clear_all_notifications(owner_id)

    other_page = await service.get_notifications(other_id)
    assert other_page.total == 1
    assert other_page.unread_count == 1
    assert other_page.items[0].id == other.id
    assert other_page.items[0].status.value == "UNREAD"
    assert await _stored_notification_count(db_session, owner_id) == 0
    assert await _stored_notification_count(db_session, other_id) == 1

    with pytest.raises(HTTPException) as read_error:
        await service.mark_as_read(other.id, owner_id)
    assert read_error.value.status_code == 404

    with pytest.raises(HTTPException) as unread_error:
        await service.mark_as_unread(other.id, owner_id)
    assert unread_error.value.status_code == 404

    with pytest.raises(HTTPException) as delete_error:
        await service.delete_notification(other.id, owner_id)
    assert delete_error.value.status_code == 404
    assert await _stored_notification_count(db_session, other_id) == 1
