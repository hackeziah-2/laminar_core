from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import PH_TZ
from app.models.advisory_notification_log import AdvisoryNotificationLog
from app.models.notification import Notification
from app.models.personnel_compliance import (
    PersonnelCompliance,
    PersonnelComplianceItemType,
)
from app.repository.advisory_notification_log import build_advisory_idempotency_key
from app.services.advisory_notification_service import run_remaining_30_days_advisory_notifications
from tests.factories.rbac import seed_account, seed_role


@pytest.mark.asyncio
async def test_advisory_notification_service_sends_once_and_logs(
    db_session: AsyncSession,
):
    qe_role_id = await seed_role(db_session, name="Quality Engineer")
    qm_role_id = await seed_role(db_session, name="Quality Manager")
    viewer_role_id = await seed_role(db_session, name="Viewer")
    await seed_account(db_session, role_id=qe_role_id)
    await seed_account(db_session, role_id=qm_role_id)
    account_id = await seed_account(db_session, role_id=viewer_role_id)

    today_ph = datetime.now(PH_TZ).date()
    advisory = PersonnelCompliance(
        account_information_id=account_id,
        item_type=PersonnelComplianceItemType.AUTH_EXPIRY,
        expiry_date=today_ph + timedelta(days=30),
        is_withhold=False,
    )
    db_session.add(advisory)
    await db_session.commit()
    await db_session.refresh(advisory)

    first_run = await run_remaining_30_days_advisory_notifications(db_session)
    second_run = await run_remaining_30_days_advisory_notifications(db_session)

    assert first_run["matched"] == 1
    assert first_run["sent"] == 1
    assert second_run["matched"] == 1
    assert second_run["sent"] == 0
    assert second_run["skipped"] == 1

    notification_rows = (
        await db_session.execute(select(Notification).where(Notification.module_name == "advisory"))
    ).scalars().all()
    assert len(notification_rows) == 2  # QE + QM recipients
    for row in notification_rows:
        assert row.notification_metadata["url"] == "regulatory-compliance/advisory"
        assert row.notification_metadata["search"]

    logs = (await db_session.execute(select(AdvisoryNotificationLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].idempotency_key == build_advisory_idempotency_key(
        regulatory_compliance="personnel-compliance",
        advisory_id=advisory.id,
        expiry_date=advisory.expiry_date,
    )


@pytest.mark.asyncio
async def test_advisory_notification_service_skips_if_no_quality_roles(
    db_session: AsyncSession,
):
    role_id = await seed_role(db_session, name="Non Quality Role")
    account_id = await seed_account(db_session, role_id=role_id)
    today_ph = datetime.now(PH_TZ).date()
    advisory = PersonnelCompliance(
        account_information_id=account_id,
        item_type=PersonnelComplianceItemType.AUTH_EXPIRY,
        expiry_date=today_ph + timedelta(days=30),
        is_withhold=False,
    )
    db_session.add(advisory)
    await db_session.commit()

    result = await run_remaining_30_days_advisory_notifications(db_session)

    assert result["matched"] == 1
    assert result["sent"] == 0
    assert result["skipped"] == 1
    logs = (await db_session.execute(select(AdvisoryNotificationLog))).scalars().all()
    assert logs == []
