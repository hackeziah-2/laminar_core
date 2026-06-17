"""Notification business logic and reusable service API."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_time import format_time_ago
from app.enums.notification import NotificationListStatusFilter, NotificationStatus
from app.models.notification import Notification
from app.repository import notification as notification_repo
from app.schemas.notification_schema import (
    NotificationCreate,
    NotificationPagedResponse,
    NotificationRead,
    NotificationUnreadCountResponse,
)
from app.websocket.notification_manager import (
    NotificationConnectionManager,
    get_notification_manager,
)
from app.websocket.notification_broker import publish_notification_realtime

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates notification persistence, retrieval, and realtime delivery."""

    def __init__(
        self,
        session: AsyncSession,
        ws_manager: Optional[NotificationConnectionManager] = None,
    ) -> None:
        self.session = session
        self.ws_manager = ws_manager or get_notification_manager()

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _resolve_atl_aircraft_id(cls, metadata: Dict[str, Any]) -> Optional[int]:
        """Resolve aircraft id from legacy/new metadata shapes."""
        for key in ("aircraft_id", "aircraft_fk"):
            aircraft_id = cls._coerce_int(metadata.get(key))
            if aircraft_id is not None:
                return aircraft_id

        aircraft = metadata.get("aircraft")
        if isinstance(aircraft, dict):
            aircraft_id = cls._coerce_int(aircraft.get("id"))
            if aircraft_id is not None:
                return aircraft_id

        filters = metadata.get("technical_logbook_filters")
        if isinstance(filters, dict):
            aircraft_id = cls._coerce_int(filters.get("aircraft_id"))
            if aircraft_id is not None:
                return aircraft_id

        return None

    @staticmethod
    def _build_atl_technical_logbook_url(
        *,
        sequence_no: Optional[str],
        aircraft_id: Optional[int],
        atl_batch_fk: Optional[int],
    ) -> str:
        seq = (sequence_no or "").strip() or "unknown"
        return (
            f"/technical-logbook/sequence_no={seq}"
            f"?aircraft_id={aircraft_id}/atl_batch_fk={atl_batch_fk}"
        )

    @classmethod
    def _normalize_metadata(
        cls,
        *,
        reference_type: Optional[str],
        reference_id: Optional[int],
        metadata: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not metadata:
            return metadata
        if str(reference_type or "").upper() != "ATL":
            return metadata

        normalized = dict(metadata)
        atl_batch_fk = normalized.get("atl_batch_fk", normalized.get("batch_id"))
        aircraft_id = cls._resolve_atl_aircraft_id(normalized)
        normalized["atl_batch_fk"] = atl_batch_fk
        normalized["batch_id"] = atl_batch_fk
        normalized["atl_id"] = normalized.get("atl_id", reference_id)
        normalized["aircraft_id"] = aircraft_id
        if isinstance(normalized.get("aircraft"), dict) and aircraft_id is not None:
            normalized["aircraft"] = {**normalized["aircraft"], "id": aircraft_id}
        normalized["url"] = cls._build_atl_technical_logbook_url(
            sequence_no=normalized.get("sequence_no"),
            aircraft_id=aircraft_id,
            atl_batch_fk=atl_batch_fk,
        )
        return normalized

    @classmethod
    def to_read_schema(cls, notification: Notification) -> NotificationRead:
        """Map ORM row to frontend-ready response."""
        metadata = cls._normalize_metadata(
            reference_type=notification.reference_type,
            reference_id=notification.reference_id,
            metadata=notification.notification_metadata,
        )
        return NotificationRead(
            id=notification.id,
            uuid=notification.uuid,
            sender_initials=notification.sender_initials,
            title=notification.title,
            message=notification.message,
            module_name=notification.module_name,
            type=notification.type,
            severity=notification.severity,
            status=notification.status,
            reference_id=notification.reference_id,
            reference_type=notification.reference_type,
            notification_metadata=metadata,
            created_at=notification.created_at,
            read_at=notification.read_at,
            archived_at=notification.archived_at,
            time_ago=format_time_ago(notification.created_at),
        )

    async def create_notification(
        self,
        data: NotificationCreate,
        *,
        push_realtime: bool = True,
    ) -> NotificationRead:
        """Create a notification and optionally push it over WebSocket."""
        row = await notification_repo.create_notification(self.session, data)
        unread_count = await notification_repo.count_unread_for_recipient(
            self.session,
            data.recipient_account_id,
        )
        read_schema = self.to_read_schema(row)

        if push_realtime:
            await self._push_new_notification(
                recipient_account_id=data.recipient_account_id,
                notification=read_schema,
                unread_count=unread_count,
            )
        return read_schema

    async def get_notifications(
        self,
        recipient_account_id: int,
        *,
        status_filter: NotificationListStatusFilter = NotificationListStatusFilter.ALL,
        page: int = 1,
        limit: int = 20,
    ) -> NotificationPagedResponse:
        """Paginated notification list for the authenticated recipient."""
        offset = (page - 1) * limit
        items, total = await notification_repo.list_notifications_for_recipient(
            self.session,
            recipient_account_id=recipient_account_id,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        unread_count = await notification_repo.count_unread_for_recipient(
            self.session,
            recipient_account_id,
        )
        return NotificationPagedResponse(
            items=[self.to_read_schema(item) for item in items],
            page=page,
            limit=limit,
            total=total,
            total_pages=notification_repo.compute_total_pages(total, limit),
            unread_count=unread_count,
        )

    async def get_unread_count(self, recipient_account_id: int) -> NotificationUnreadCountResponse:
        count = await notification_repo.count_unread_for_recipient(
            self.session,
            recipient_account_id,
        )
        return NotificationUnreadCountResponse(unread_count=count)

    async def mark_as_read(
        self,
        notification_id: int,
        recipient_account_id: int,
    ) -> NotificationRead:
        notification = await self._get_owned_notification(notification_id, recipient_account_id)
        if notification.status != NotificationStatus.UNREAD:
            return self.to_read_schema(notification)
        updated = await notification_repo.mark_notification_read(self.session, notification)
        unread_count = await notification_repo.count_unread_for_recipient(
            self.session,
            recipient_account_id,
        )
        read_schema = self.to_read_schema(updated)
        await self._push_unread_count(recipient_account_id, unread_count)
        return read_schema

    async def mark_all_as_read(self, recipient_account_id: int) -> int:
        updated_count = await notification_repo.mark_all_notifications_read(
            self.session,
            recipient_account_id,
        )
        await self._push_unread_count(recipient_account_id, 0)
        return updated_count

    async def archive_notification(
        self,
        notification_id: int,
        recipient_account_id: int,
    ) -> NotificationRead:
        notification = await self._get_owned_notification(notification_id, recipient_account_id)
        updated = await notification_repo.archive_notification(self.session, notification)
        unread_count = await notification_repo.count_unread_for_recipient(
            self.session,
            recipient_account_id,
        )
        await self._push_unread_count(recipient_account_id, unread_count)
        return self.to_read_schema(updated)

    async def clear_all_notifications(self, recipient_account_id: int) -> int:
        archived_count = await notification_repo.archive_all_notifications(
            self.session,
            recipient_account_id,
        )
        await self._push_unread_count(recipient_account_id, 0)
        return archived_count

    async def _get_owned_notification(
        self,
        notification_id: int,
        recipient_account_id: int,
    ) -> Notification:
        notification = await notification_repo.get_notification_for_recipient(
            self.session,
            notification_id,
            recipient_account_id,
        )
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        return notification

    async def _push_new_notification(
        self,
        *,
        recipient_account_id: int,
        notification: NotificationRead,
        unread_count: int,
    ) -> None:
        payload = {
            "event": "new_notification",
            "data": {
                "id": notification.id,
                "uuid": str(notification.uuid),
                "title": notification.title,
                "message": notification.message,
                "module_name": notification.module_name,
                "type": notification.type.value,
                "severity": notification.severity.value,
                "status": notification.status.value,
                "reference_id": notification.reference_id,
                "reference_type": notification.reference_type,
                "metadata": notification.metadata,
                "time_ago": notification.time_ago,
                "unread_count": unread_count,
            },
        }
        try:
            await publish_notification_realtime(recipient_account_id, payload)
        except Exception:
            logger.warning(
                "Realtime notification push failed for account_id=%s",
                recipient_account_id,
                exc_info=True,
            )

    async def _push_unread_count(self, recipient_account_id: int, unread_count: int) -> None:
        payload = {
            "event": "unread_count_updated",
            "data": {"unread_count": unread_count},
        }
        try:
            await publish_notification_realtime(recipient_account_id, payload)
        except Exception:
            logger.warning(
                "Unread count push failed for account_id=%s",
                recipient_account_id,
                exc_info=True,
            )
