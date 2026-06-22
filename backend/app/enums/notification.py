"""Notification domain enumerations."""

import enum


class NotificationType(str, enum.Enum):
    SYSTEM = "SYSTEM"
    APPROVAL = "APPROVAL"
    REMINDER = "REMINDER"
    ALERT = "ALERT"
    INFO = "INFO"


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NotificationStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"


class NotificationListStatusFilter(str, enum.Enum):
    """Query filter for notification list endpoints."""

    ALL = "all"
    UNREAD = "unread"
    READ = "read"
