"""Notification REST and WebSocket API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.core.security import decode_access_token
from app.database import AsyncSessionLocal, get_session
from app.enums.notification import NotificationListStatusFilter
from app.models.account import AccountInformation
from app.repository.account_auth import get_account_by_id
from app.schemas.notification_schema import (
    NotificationPagedResponse,
    NotificationRead,
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


@router.get("", response_model=NotificationPagedResponse)
@router.get("/", response_model=NotificationPagedResponse, include_in_schema=False)
async def api_list_notifications(
    status: NotificationListStatusFilter = Query(
        NotificationListStatusFilter.ALL,
        description="Filter: all, unread, or read (archived excluded).",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """List notifications for the authenticated user."""
    return await service.get_notifications(
        current_account.id,
        status_filter=status,
        page=page,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def api_unread_count(
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Return unread notification count for the bell badge."""
    return await service.get_unread_count(current_account.id)


@router.patch("/read-all")
async def api_mark_all_read(
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Mark all unread notifications as read."""
    updated_count = await service.mark_all_as_read(current_account.id)
    return {"updated_count": updated_count}


@router.patch("/clear-all")
async def api_clear_all(
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Soft-archive all notifications (clear all)."""
    archived_count = await service.clear_all_notifications(current_account.id)
    return {"archived_count": archived_count}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def api_mark_read(
    notification_id: int,
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Mark a single notification as read."""
    return await service.mark_as_read(notification_id, current_account.id)


@router.patch("/{notification_id}/archive", response_model=NotificationRead)
async def api_archive_notification(
    notification_id: int,
    current_account: AccountInformation = Depends(get_current_active_account),
    service: NotificationService = Depends(_notification_service),
):
    """Archive a single notification."""
    return await service.archive_notification(notification_id, current_account.id)


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
