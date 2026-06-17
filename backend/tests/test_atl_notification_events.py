"""Tests for ATL status-change notification event publisher."""

from datetime import date, time
from types import SimpleNamespace
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.atl_notification_events import (
    ATL_STATUS_NOTIFICATION_ROLE_MAP,
    publish_atl_status_change_notification,
    resolve_atl_status_change_recipient_ids,
)
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, TypeEnum, WorkStatus
from app.repository.aircraft_technical_log import bulk_update_aircraft_technical_log_work_status
from tests.factories.rbac import seed_account, seed_role


def _fake_atl(*, created_by: Optional[int] = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=123,
        sequence_no="000123",
        created_by=created_by,
        aircraft_fk=1,
        atl_batch_fk=5,
    )


@pytest.mark.asyncio
async def test_no_notification_when_status_does_not_change(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    calls: list[int] = []

    async def _fake_publish(*args, **kwargs):
        calls.append(kwargs["recipient_account_id"])
        return object()

    monkeypatch.setattr(
        "app.events.atl_notification_events.publish_notification_event",
        _fake_publish,
    )

    notified = await publish_atl_status_change_notification(
        db_session,
        atl=_fake_atl(created_by=1),
        old_status=WorkStatus.PENDING,
        new_status=WorkStatus.PENDING,
        changed_by_account=None,
    )
    assert notified == []
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("new_status", "role_names"),
    [
        (WorkStatus.AWAITING_ATTACHMENT, ["Technical Publication"]),
        (WorkStatus.PENDING, ["Maintenance Manager"]),
        (WorkStatus.APPROVED, ["Quality Manager"]),
        (WorkStatus.COMPLETED, ["Admin", "Maintenance Manager"]),
        (WorkStatus.REJECTED_QUALITY, ["Maintenance Planner"]),
        (WorkStatus.REJECTED_MAINTENANCE, ["Maintenance Planner"]),
    ],
)
async def test_status_rules_notify_creator_and_roles(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    new_status: WorkStatus,
    role_names: list[str],
):
    creator_role_id = await seed_role(db_session, name="Creator Role")
    creator_id = await seed_account(db_session, role_id=creator_role_id)

    role_account_ids: list[int] = []
    for role_name in role_names:
        role_id = await seed_role(db_session, name=role_name)
        role_account_ids.append(await seed_account(db_session, role_id=role_id))
    await db_session.commit()

    recipients: list[int] = []

    async def _fake_publish(*args, **kwargs):
        recipients.append(kwargs["recipient_account_id"])
        return object()

    monkeypatch.setattr(
        "app.events.atl_notification_events.publish_notification_event",
        _fake_publish,
    )

    notified = await publish_atl_status_change_notification(
        db_session,
        atl=_fake_atl(created_by=creator_id),
        old_status=WorkStatus.FOR_REVIEW,
        new_status=new_status,
        changed_by_account=None,
    )

    expected = sorted({creator_id, *role_account_ids})
    assert sorted(notified) == expected
    assert sorted(recipients) == expected


@pytest.mark.asyncio
async def test_changed_by_user_is_excluded_from_recipients(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    manager_role_id = await seed_role(db_session, name="Maintenance Manager")
    actor_id = await seed_account(db_session, role_id=manager_role_id)
    await db_session.commit()
    actor = await db_session.get(AccountInformation, actor_id)
    assert actor is not None

    recipients: list[int] = []

    async def _fake_publish(*args, **kwargs):
        recipients.append(kwargs["recipient_account_id"])
        return object()

    monkeypatch.setattr(
        "app.events.atl_notification_events.publish_notification_event",
        _fake_publish,
    )

    # creator is actor; role recipient is also actor -> no notifications
    notified = await publish_atl_status_change_notification(
        db_session,
        atl=_fake_atl(created_by=actor_id),
        old_status=WorkStatus.FOR_REVIEW,
        new_status=WorkStatus.PENDING,
        changed_by_account=actor,
    )

    assert notified == []
    assert recipients == []


def test_recipient_deduplication_helper_removes_duplicates_and_actor():
    creator_id = 10
    role_accounts = [
        SimpleNamespace(id=10),  # same as creator
        SimpleNamespace(id=20),
        SimpleNamespace(id=20),  # duplicate role user
    ]
    recipient_ids = resolve_atl_status_change_recipient_ids(
        creator_account_id=creator_id,
        role_accounts=role_accounts,
        changed_by_account_id=10,
    )
    assert recipient_ids == {20}


@pytest.mark.asyncio
async def test_bulk_work_status_update_publishes_notifications(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    creator_role_id = await seed_role(db_session, name="Creator Role")
    creator_id = await seed_account(db_session, role_id=creator_role_id)
    manager_role_id = await seed_role(db_session, name="Maintenance Manager")
    await seed_account(db_session, role_id=manager_role_id)
    actor_role_id = await seed_role(db_session, name="Admin")
    actor_id = await seed_account(db_session, role_id=actor_role_id)

    aircraft = Aircraft(
        registration="N-BULK-ATL",
        model="737",
        msn="MSN-BULK",
        base="Base",
        ownership="Owner",
        status="Active",
    )
    db_session.add(aircraft)
    await db_session.flush()

    atl = AircraftTechnicalLog(
        aircraft_fk=aircraft.id,
        sequence_no="000777",
        nature_of_flight=TypeEnum.TR,
        origin_station="ORG",
        origin_date=date.today(),
        origin_time=time(10, 0),
        destination_station="DST",
        destination_date=date.today(),
        destination_time=time(12, 0),
        number_of_landings=1,
        work_status=WorkStatus.FOR_REVIEW,
        created_by=creator_id,
    )
    db_session.add(atl)
    await db_session.commit()
    await db_session.refresh(atl)

    actor = await db_session.get(AccountInformation, actor_id)
    assert actor is not None

    recipients: list[int] = []

    async def _fake_publish(*args, **kwargs):
        recipients.append(kwargs["recipient_account_id"])
        return object()

    monkeypatch.setattr(
        "app.events.atl_notification_events.publish_notification_event",
        _fake_publish,
    )

    await bulk_update_aircraft_technical_log_work_status(
        db_session,
        atl_ids=[atl.id],
        work_status=WorkStatus.PENDING,
        current_account=actor,
        audit_user=actor,
    )

    assert recipients


def test_status_role_map_covers_required_rules():
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.AWAITING_ATTACHMENT] == [
        "Technical Publication"
    ]
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.PENDING] == [
        "Maintenance Manager"
    ]
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.APPROVED] == [
        "Quality Manager"
    ]
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.COMPLETED] == [
        "Admin",
        "Maintenance Manager",
    ]
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.REJECTED_QUALITY] == [
        "Maintenance Planner"
    ]
    assert ATL_STATUS_NOTIFICATION_ROLE_MAP[WorkStatus.REJECTED_MAINTENANCE] == [
        "Maintenance Planner"
    ]
