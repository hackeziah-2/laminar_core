"""Notification REST and WebSocket API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.core.security import decode_access_token
from app.database import AsyncSessionLocal, get_session
from app.enums.notification import NotificationListStatusFilter
from app.models.account import AccountInformation
from app.repository.account_auth import get_account_by_id
from app.schemas.notification_schema import (
    NotificationMutationResponse,
    NotificationPagedResponse,
    NotificationRead,
    NotificationStateResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import NotificationService
from app.websocket.notification_manager import get_notification_manager

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
)


def _notification_service(session: AsyncSession = Depends(get_session)) -> NotificationService:
    return NotificationService(session)


def _resolve_recipient_account_id(
    recipient_account: Optional[int],
    current_account: AccountInformation,
) -> int:
    """Count or list for recipient_account when sent; it must be the signed-in account."""
    if recipient_account is None:
        return current_account.id
    if recipient_account != current_account.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access another account's notifications.",
        )
    return recipient_account


@router.get("", response_model=NotificationPagedResponse)
@router.get("/", response_model=NotificationPagedResponse, include_in_schema=False)
async def api_list_notifications(
    status: NotificationListStatusFilter = Query(
        NotificationListStatusFilter.ALL,
        description="Filter: all, unread, or read (archived excluded).",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    recipient_account: Optional[int] = Query(
        None,
        description="Account id to list. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """List notifications for the authenticated user."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    return await service.get_notifications(
        recipient_id,
        status_filter=status,
        page=page,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def api_unread_count(
    recipient_account: Optional[int] = Query(
        None,
        description="Account id whose unread notifications to count. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Return unread notification count for the bell badge."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    return await service.get_unread_count(recipient_id)


def _state_response(
    notification: NotificationRead,
    notice: str,
    counts: NotificationUnreadCountResponse,
) -> NotificationStateResponse:
    return NotificationStateResponse(
        notice=notice,
        unread_count=counts.unread_count,
        total=counts.total,
        read_count=counts.read_count,
        **notification.dict(),
    )


def _mutation_response(
    message: str,
    counts: NotificationUnreadCountResponse,
    *,
    updated_count: int = 0,
    deleted_count: int = 0,
) -> NotificationMutationResponse:
    return NotificationMutationResponse(
        message=message,
        unread_count=counts.unread_count,
        total=counts.total,
        read_count=counts.read_count,
        updated_count=updated_count,
        deleted_count=deleted_count,
    )


@router.patch("/read-all", response_model=NotificationMutationResponse)
async def api_mark_all_read(
    recipient_account: Optional[int] = Query(
        None,
        description="Account id to update. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Mark every unread notification in the authenticated user's inbox as read."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    updated_count = await service.mark_all_as_read(recipient_id)
    counts = await service.inbox_counts(recipient_id)
    return _mutation_response(
        "All notifications marked as read.",
        counts,
        updated_count=updated_count,
    )


@router.patch("/clear-all", response_model=NotificationMutationResponse)
async def api_clear_all(
    recipient_account: Optional[int] = Query(
        None,
        description="Account id to clear. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Permanently delete every notification belonging to the authenticated user."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    deleted_count = await service.clear_all_notifications(recipient_id)
    counts = await service.inbox_counts(recipient_id)
    message = (
        "All notifications deleted."
        if deleted_count
        else "No notifications to delete."
    )
    return _mutation_response(message, counts, deleted_count=deleted_count)


@router.patch("/{notification_id}/read", response_model=NotificationStateResponse)
async def api_mark_read(
    notification_id: int,
    recipient_account: Optional[int] = Query(
        None,
        description="Account id that owns the notification. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Mark one notification in the authenticated user's inbox as read."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    notification = await service.mark_as_read(notification_id, recipient_id)
    counts = await service.inbox_counts(recipient_id)
    return _state_response(notification, "Notification marked as read.", counts)


@router.patch("/{notification_id}/unread", response_model=NotificationStateResponse)
async def api_mark_unread(
    notification_id: int,
    recipient_account: Optional[int] = Query(
        None,
        description="Account id that owns the notification. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Mark one notification in the authenticated user's inbox as unread."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    notification = await service.mark_as_unread(notification_id, recipient_id)
    counts = await service.inbox_counts(recipient_id)
    return _state_response(notification, "Notification marked as unread.", counts)


@router.delete("/{notification_id}", response_model=NotificationMutationResponse)
async def api_delete_notification(
    notification_id: int,
    recipient_account: Optional[int] = Query(
        None,
        description="Account id that owns the notification. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Permanently delete one notification from the authenticated user's inbox."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    await service.delete_notification(notification_id, recipient_id)
    counts = await service.inbox_counts(recipient_id)
    return _mutation_response(
        "Notification deleted.",
        counts,
        deleted_count=1,
    )


@router.patch("/{notification_id}/archive", response_model=NotificationRead)
async def api_archive_notification(
    notification_id: int,
    recipient_account: Optional[int] = Query(
        None,
        description="Account id that owns the notification. Must be the authenticated account.",
    ),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Archive a single notification owned by the authenticated user."""
    recipient_id = _resolve_recipient_account_id(recipient_account, current_account)
    return await service.archive_notification(notification_id, recipient_id)


async def _authenticate_websocket(
    websocket: WebSocket,
    session: AsyncSession,
) -> AccountInformation:
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    account_id = payload.get("sub")
    if account_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        account_pk = int(account_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    account = await get_account_by_id(session, account_pk)
    if not account or not account.status:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    return account


@router.websocket("/ws")
async def notification_websocket(websocket: WebSocket):
    """Realtime notification channel for the authenticated user."""
    manager = get_notification_manager()
    async with AsyncSessionLocal() as session:
        try:
            account = await _authenticate_websocket(websocket, session)
        except HTTPException:
            await websocket.close(code=4401)
            return

        await manager.connect(account.id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(account.id, websocket)
