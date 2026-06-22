"""Tests for Fleet Daily Update bulk notification events."""

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.fleet_daily_update_notification_events import (
    FLEET_DAILY_UPDATE_NOTIFICATION_ROLES,
    publish_fleet_daily_update_bulk_notification,
)
from tests.factories.rbac import seed_account, seed_role


def _fake_fleet_obj(update_id: int, registration: str):
    return SimpleNamespace(
        id=update_id,
        aircraft=SimpleNamespace(registration=registration),
    )


@pytest.mark.asyncio
async def test_bulk_notification_publishes_to_required_roles_and_formats_message(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    recipient_ids = []
    for role_name in FLEET_DAILY_UPDATE_NOTIFICATION_ROLES:
        role_id = await seed_role(db_session, name=role_name)
        recipient_ids.append(await seed_account(db_session, role_id=role_id))
    await db_session.commit()

    calls = []

    async def _fake_publish(*args, **kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(
        "app.events.fleet_daily_update_notification_events.publish_notification_event",
        _fake_publish,
    )

    notified = await publish_fleet_daily_update_bulk_notification(
        db_session,
        updated_objects=[
            _fake_fleet_obj(11, "RP-3232"),
            _fake_fleet_obj(22, "RP-2323"),
            _fake_fleet_obj(33, "RP-2323"),
        ],
        changed_by_account=None,
    )

    expected_message = (
        "Fleet Daily Update was updated for aircraft RP-2323, RP-3232"
    )
    assert sorted(notified) == sorted(recipient_ids)
    assert len(calls) == 3
    assert {c["recipient_account_id"] for c in calls} == set(recipient_ids)
    assert all(c["title"] == "Fleet Daily Update Updated" for c in calls)
    assert all(c["message"] == expected_message for c in calls)
    assert all(c["module_name"] == "daily-update" for c in calls)
    assert all(c["metadata"]["url"] == "daily-update" for c in calls)


@pytest.mark.asyncio
async def test_bulk_notification_skips_when_no_updated_objects(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    async def _fake_publish(*args, **kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(
        "app.events.fleet_daily_update_notification_events.publish_notification_event",
        _fake_publish,
    )

    notified = await publish_fleet_daily_update_bulk_notification(
        db_session,
        updated_objects=[],
        changed_by_account=None,
    )
    assert notified == []
    assert calls == []
