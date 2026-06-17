"""ATL status-change event publisher."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.notification import NotificationSeverity, NotificationType
from app.events.notification_events import publish_notification_event
from app.models.account import AccountInformation
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from app.repository.user_repository import get_active_accounts_by_roles

ATL_STATUS_NOTIFICATION_ROLE_MAP: Dict[WorkStatus, List[str]] = {
    WorkStatus.AWAITING_ATTACHMENT: ["Technical Publication"],
    WorkStatus.PENDING: ["Maintenance Manager"],
    WorkStatus.APPROVED: ["Quality Manager"],
    WorkStatus.COMPLETED: ["Admin", "Maintenance Manager"],
    WorkStatus.REJECTED_QUALITY: ["Maintenance Planner"],
    WorkStatus.REJECTED_MAINTENANCE: ["Maintenance Planner"],
}


def _to_work_status(value: Union[WorkStatus, str, None]) -> Optional[WorkStatus]:
    if value is None:
        return None
    if isinstance(value, WorkStatus):
        return value
    try:
        return WorkStatus(str(value))
    except ValueError:
        return None


def _build_atl_technical_logbook_url(atl: AircraftTechnicalLog) -> str:
    """Deep-link to technical logbook filtered by ATL context."""
    sequence_no = (atl.sequence_no or "").strip() or str(atl.id)
    return (
        f"/technical-logbook/sequence_no={sequence_no}"
        f"?aircraft_id={atl.aircraft_fk}/atl_batch_fk={atl.atl_batch_fk}"
    )


def resolve_atl_status_change_recipient_ids(
    *,
    creator_account_id: Optional[int],
    role_accounts: Sequence[AccountInformation],
    changed_by_account_id: Optional[int],
) -> Set[int]:
    """Build unique recipients: ATL creator + role recipients, excluding actor."""
    recipient_ids: Set[int] = set()
    if creator_account_id is not None:
        recipient_ids.add(creator_account_id)
    recipient_ids.update(account.id for account in role_accounts)
    if changed_by_account_id is not None:
        recipient_ids.discard(changed_by_account_id)
    return recipient_ids


async def publish_atl_status_change_notification(
    session: AsyncSession,
    *,
    atl: AircraftTechnicalLog,
    old_status: Union[WorkStatus, str, None],
    new_status: Union[WorkStatus, str, None],
    changed_by_account: Optional[AccountInformation] = None,
) -> List[int]:
    """Publish ATL status-change notifications after the ATL transaction commits."""
    old_work_status = _to_work_status(old_status)
    new_work_status = _to_work_status(new_status)
    if new_work_status is None or old_work_status == new_work_status:
        return []

    target_roles = ATL_STATUS_NOTIFICATION_ROLE_MAP.get(new_work_status, [])
    role_accounts = await get_active_accounts_by_roles(session, target_roles)
    recipient_ids = resolve_atl_status_change_recipient_ids(
        creator_account_id=atl.created_by,
        role_accounts=role_accounts,
        changed_by_account_id=changed_by_account.id if changed_by_account else None,
    )
    if not recipient_ids:
        return []

    severity = NotificationSeverity.INFO
    if new_work_status in (WorkStatus.REJECTED_QUALITY, WorkStatus.REJECTED_MAINTENANCE):
        severity = NotificationSeverity.WARNING
    elif new_work_status in (WorkStatus.APPROVED, WorkStatus.COMPLETED):
        severity = NotificationSeverity.SUCCESS

    title = f"ATL Status Updated: {new_work_status.value}"
    old_label = old_work_status.value if old_work_status else "NEW"
    message = (
        f"ATL #{(atl.sequence_no or '').strip() or atl.id} status changed from "
        f"{old_label} to {new_work_status.value}."
    )
    technical_logbook_filters = {
        "sequence_no": atl.sequence_no,
        "batch_id": atl.atl_batch_fk,
        "atl_id": atl.id,
        "aircraft_id": atl.aircraft_fk,
    }
    metadata = {
        "old_status": old_label,
        "new_status": new_work_status.value,
        "sequence_no": atl.sequence_no,
        "atl_batch_fk": atl.atl_batch_fk,
        "batch_id": atl.atl_batch_fk,
        "atl_id": atl.id,
        "aircraft_id": atl.aircraft_fk,
        "technical_logbook_filters": technical_logbook_filters,
        "aircraft": {
            "id": atl.aircraft_fk,
            "registration": getattr(getattr(atl, "aircraft", None), "registration", None),
            "model": getattr(getattr(atl, "aircraft", None), "model", None),
        },
        "url": _build_atl_technical_logbook_url(atl),
    }

    notified_ids: List[int] = []
    for recipient_id in sorted(recipient_ids):
        created = await publish_notification_event(
            session,
            recipient_account_id=recipient_id,
            sender_account=changed_by_account,
            title=title,
            message=message,
            module_name="ATL",
            notification_type=NotificationType.APPROVAL,
            severity=severity,
            reference_id=atl.id,
            reference_type="ATL",
            metadata=metadata,
        )
        if created:
            notified_ids.append(recipient_id)

    return notified_ids
