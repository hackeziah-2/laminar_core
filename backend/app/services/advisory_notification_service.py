"""Scheduled advisory notification service."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import PH_TZ, ph_now
from app.events.advisory_notification_events import publish_advisory_notification_event
from app.models.advisory_notification_log import AdvisoryNotificationLog
from app.repository.advisory import list_advisory_items_by_remaining_validity
from app.repository.advisory_notification_log import (
    build_advisory_idempotency_key,
    get_log_by_idempotency_key,
)
from app.schemas.advisory_schema import AdvisoryItem

logger = logging.getLogger(__name__)

ADVISORY_NOTIFICATION_ROLES = ["Quality Engineer", "Quality Manager"]
ADVISORY_NOTIFICATION_TITLE = "Regulatory Compliance Advisory"
ADVISORY_NOTIFICATION_TYPE = "remaining_30_days"
ADVISORY_NOTIFICATION_REMAINING_VALIDITY = 30


def _advisory_metadata(item: AdvisoryItem) -> dict:
    return {
        "module_name": "advisory",
        "url": "regulatory-compliance/advisory",
        "search": item.ITEM,
    }


async def _publish_for_item(
    session: AsyncSession,
    *,
    item: AdvisoryItem,
) -> int:
    message = (
        f"{item.ITEM} will expire in 30 days. "
        f"Expiry Date: {item.EXPIRY.isoformat() if item.EXPIRY else ''}"
    )
    return await publish_advisory_notification_event(
        session,
        title=ADVISORY_NOTIFICATION_TITLE,
        message=message,
        module_name="advisory",
        recipients_role_names=ADVISORY_NOTIFICATION_ROLES,
        metadata=_advisory_metadata(item),
        reference_id=item.id,
    )


async def run_remaining_30_days_advisory_notifications(
    session: AsyncSession,
) -> dict:
    """
    Trigger advisory notifications for records at exactly 30 remaining validity days.

    This routine is idempotent via advisory_notification_logs.idempotency_key.
    """
    now_ph = datetime.now(PH_TZ)
    logger.info(
        "Starting advisory 30-day notification job at %s",
        now_ph.isoformat(),
    )
    candidate_items = await list_advisory_items_by_remaining_validity(
        session,
        remaining_validity=ADVISORY_NOTIFICATION_REMAINING_VALIDITY,
    )
    candidate_items = [
        item
        for item in candidate_items
        if item.id
        and item.EXPIRY
        and item.REMAINING_VALIDITY == ADVISORY_NOTIFICATION_REMAINING_VALIDITY
    ]
    if not candidate_items:
        logger.info("No advisory items matched remaining validity = 30")
        return {"matched": 0, "sent": 0, "skipped": 0}

    sent = 0
    skipped = 0
    for item in candidate_items:
        assert item.id is not None
        assert item.EXPIRY is not None
        idempotency_key = build_advisory_idempotency_key(
            regulatory_compliance=item.regulatory_compliance,
            advisory_id=item.id,
            expiry_date=item.EXPIRY,
        )
        existing = await get_log_by_idempotency_key(
            session,
            idempotency_key=idempotency_key,
        )
        if existing:
            skipped += 1
            continue

        try:
            published_count = await _publish_for_item(session, item=item)
            if published_count == 0:
                skipped += 1
                logger.info(
                    "Skipping advisory item id=%s due to zero recipients",
                    item.id,
                )
                continue
            session.add(
                AdvisoryNotificationLog(
                    advisory_source_id=item.id,
                    regulatory_compliance=item.regulatory_compliance,
                    item=item.ITEM,
                    expiry_date=item.EXPIRY,
                    notification_type=ADVISORY_NOTIFICATION_TYPE,
                    idempotency_key=idempotency_key,
                    triggered_at=ph_now(),
                )
            )
            await session.commit()
            sent += 1
        except IntegrityError:
            await session.rollback()
            skipped += 1
            logger.warning("Skipped duplicate advisory notification key=%s", idempotency_key)
            continue
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed advisory notification for regulatory_compliance=%s id=%s",
                item.regulatory_compliance,
                item.id,
            )
            raise
    logger.info(
        "Completed advisory 30-day notification job matched=%s sent=%s skipped=%s",
        len(candidate_items),
        sent,
        skipped,
    )
    return {"matched": len(candidate_items), "sent": sent, "skipped": skipped}
