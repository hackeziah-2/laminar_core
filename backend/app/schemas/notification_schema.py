"""Pydantic schemas for the Notification module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.enums.notification import (
    NotificationListStatusFilter,
    NotificationSeverity,
    NotificationStatus,
    NotificationType,
)


class NotificationCreate(BaseModel):
    recipient_account_id: int
    sender_account_id: Optional[int] = None
    sender_initials: str = Field(..., min_length=1, max_length=5)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    module_name: str = Field(..., min_length=1, max_length=100)
    type: NotificationType
    severity: NotificationSeverity
    reference_id: Optional[int] = None
    reference_type: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None


class NotificationRead(BaseModel):
    id: int
    uuid: UUID
    sender_initials: str
    title: str
    message: str
    module_name: str
    type: NotificationType
    severity: NotificationSeverity
    status: NotificationStatus
    reference_id: Optional[int] = None
    reference_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="notification_metadata")
    created_at: datetime
    read_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    time_ago: str

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPagedResponse(BaseModel):
    items: List[NotificationRead]
    page: int
    limit: int
    total: int
    total_pages: int
    unread_count: int


class NotificationWebSocketEvent(BaseModel):
    event: str
    data: Dict[str, Any]


class NotificationListQuery(BaseModel):
    status: NotificationListStatusFilter = NotificationListStatusFilter.ALL
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
