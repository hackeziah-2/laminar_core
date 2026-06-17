"""Celery beat schedule registration."""

from __future__ import annotations

from celery.schedules import crontab

ADVISORY_REMAINING_30_DAYS_HOUR = 0
ADVISORY_REMAINING_30_DAYS_MINUTE = 1


def register_periodic_jobs(celery_app) -> None:
    """Register periodic jobs using Asia/Manila timezone from celery app config."""
    celery_app.conf.beat_schedule = {
        **(celery_app.conf.beat_schedule or {}),
        "advisory-remaining-30-days-notification": {
            "task": "app.tasks.advisory_notifications.send_advisory_remaining_30_days_notifications",
            "schedule": crontab(
                minute=ADVISORY_REMAINING_30_DAYS_MINUTE,
                hour=ADVISORY_REMAINING_30_DAYS_HOUR,
            ),
        },
    }
