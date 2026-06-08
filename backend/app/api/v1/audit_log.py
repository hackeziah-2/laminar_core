from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.audit_log import list_audit_logs
from app.schemas.audit_log_schema import AuditLogPagedResponse, AuditLogRead

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=AuditLogPagedResponse)
async def api_list_audit_logs(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    module_name: Optional[str] = Query(None),
    table_name: Optional[str] = Query(None),
    record_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    performed_by_user_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """List audit logs with optional filters and pagination."""
    offset = (page - 1) * limit
    items, total = await list_audit_logs(
        session,
        limit=limit,
        offset=offset,
        module_name=module_name,
        table_name=table_name,
        record_id=record_id,
        action=action,
        performed_by_user_id=performed_by_user_id,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditLogPagedResponse(
        page=page,
        limit=limit,
        total=total,
        items=items,
    )
