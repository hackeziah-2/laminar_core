"""Fleet Daily Update notification event publisher."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationSeverity, NotificationType
from app.events.notification_events import publish_notification_event
from app.models.account import AccountInformation
from app.models.fleet_daily_update import FleetDailyUpdate
from app.repository.user_repository import get_active_accounts_by_roles

logger = logging.getLogger(__name__)

FLEET_DAILY_UPDATE_NOTIFICATION_ROLES: List[str] = [
    "Maintenance Manager",
    "Quality Manager",
    "Maintenance Planner",
]


def resolve_fleet_daily_update_recipient_ids(
    role_accounts: Sequence[AccountInformation],
    changed_by_account_id: Optional[int],
) -> Set[int]:
    """Build unique recipients from role accounts, excluding actor."""
    recipient_ids = {account.id for account in role_accounts}
    if changed_by_account_id is not None:
        recipient_ids.discard(changed_by_account_id)
    return recipient_ids


def _registration_from_fleet_row(obj: FleetDailyUpdate) -> Optional[str]:
    """Return normalized aircraft registration from a fleet row."""
    raw = getattr(getattr(obj, "aircraft", None), "registration_no", None) or getattr(
        getattr(obj, "aircraft", None), "registration", None
    )
    if not raw:
        return None
    cleaned = str(raw).strip()
    return cleaned or None


async def publish_fleet_daily_update_bulk_notification(
    session: AsyncSession,
    *,
    updated_objects: Sequence[FleetDailyUpdate],
    changed_by_account: Optional[AccountInformation] = None,
) -> List[int]:
    """Publish one notification for the full Fleet Daily Update bulk update request."""
    if not updated_objects:
        return []

    role_accounts = await get_active_accounts_by_roles(
        session, FLEET_DAILY_UPDATE_NOTIFICATION_ROLES
    )
    recipient_ids = resolve_fleet_daily_update_recipient_ids(
        role_accounts, changed_by_account.id if changed_by_account else None
    )
    if not recipient_ids:
        return []

    registrations = sorted(
        {
            registration
            for registration in (
                _registration_from_fleet_row(obj) for obj in updated_objects
            )
            if registration
        }
    )
    if registrations:
        aircraft_text = ", ".join(registrations)
        message = f"Fleet Daily Update was updated for aircraft {aircraft_text}"
    else:
        message = "Fleet Daily Update was updated."

    title = "Fleet Daily Update Updated"
    updated_ids = sorted({obj.id for obj in updated_objects})
    metadata = {
        "url": "daily-update",
        "updated_ids": updated_ids,
        "aircraft_registrations": registrations,
    }

    notified_ids: List[int] = []
    for recipient_id in sorted(recipient_ids):
        created = await publish_notification_event(
            session,
            recipient_account_id=recipient_id,
            sender_account=changed_by_account,
            title=title,
            message=message,
            module_name="daily-update",
            notification_type=NotificationType.INFO,
            severity=NotificationSeverity.INFO,
            reference_id=updated_ids[0] if updated_ids else None,
            reference_type="FLEET_DAILY_UPDATE_BULK",
            metadata=metadata,
        )
        if created:
            notified_ids.append(recipient_id)

    logger.info(
        "Fleet Daily Update bulk notification published recipients=%s updated_ids=%s",
        len(notified_ids),
        updated_ids,
    )
    return notified_ids
