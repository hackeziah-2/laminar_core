"""Relative timestamp formatting for notification UI."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.database import PH_TZ, ph_now


def _to_ph(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=PH_TZ)
    return dt.astimezone(PH_TZ)


def format_time_ago(dt: datetime, *, now: datetime | None = None) -> str:
    """
    Format a datetime as a human-readable relative time string.

    Examples: "2 min ago", "Yesterday", "3 days ago".
    """
    reference = _to_ph(now or ph_now())
    target = _to_ph(dt)
    delta = reference - target

    if delta < timedelta(minutes=1):
        seconds = max(int(delta.total_seconds()), 0)
        if seconds <= 1:
            return "just now"
        return f"{seconds} sec ago"

    if delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() // 60)
        label = "min" if minutes == 1 else "min"
        return f"{minutes} {label} ago"

    if delta < timedelta(hours=24) and reference.date() == target.date():
        hours = int(delta.total_seconds() // 3600)
        label = "hour" if hours == 1 else "hours"
        return f"{hours} {label} ago"

    yesterday = reference.date() - timedelta(days=1)
    if target.date() == yesterday:
        return "Yesterday"

    days = (reference.date() - target.date()).days
    if days < 7:
        label = "day" if days == 1 else "days"
        return f"{days} {label} ago"

    if days < 30:
        weeks = days // 7
        label = "week" if weeks == 1 else "weeks"
        return f"{weeks} {label} ago"

    if days < 365:
        months = days // 30
        label = "month" if months == 1 else "months"
        return f"{months} {label} ago"

    years = days // 365
    label = "year" if years == 1 else "years"
    return f"{years} {label} ago"
