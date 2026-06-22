"""Service-layer tests for notifications."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationListStatusFilter, NotificationSeverity, NotificationType
from app.schemas.notification_schema import NotificationCreate
from app.services.notification_service import NotificationService
from tests.factories.notification import seed_notification
from tests.factories.rbac import seed_account, seed_role


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
async def test_clear_all_archives_notifications(db_session: AsyncSession):
    role_id = await seed_role(db_session)
    recipient_id = await seed_account(db_session, role_id=role_id)
    await db_session.commit()

    await seed_notification(db_session, recipient_account_id=recipient_id)
    await seed_notification(db_session, recipient_account_id=recipient_id, title="Second")

    service = NotificationService(db_session)
    archived_count = await service.clear_all_notifications(recipient_id)
    page = await service.get_notifications(
        recipient_id,
        status_filter=NotificationListStatusFilter.ALL,
    )

    assert archived_count == 2
    assert page.total == 0
