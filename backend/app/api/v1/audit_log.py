from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.schemas.audit_log_schema import (
    AuditLogDetail,
    AuditLogFilterOptions,
    AuditLogPagedResponse,
)
from app.services.audit_log_service import (
    fetch_audit_log_detail,
    fetch_audit_log_filter_options,
    fetch_audit_logs,
)

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


def _resolve_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Accept both start_date/end_date and legacy date_from/date_to."""
    resolved_from = start_date or date_from
    resolved_to = end_date or date_to
    return resolved_from, resolved_to


@router.get("/filter-options", response_model=AuditLogFilterOptions)
async def api_audit_log_filter_options(
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Distinct module and user values for audit log filters."""
    return await fetch_audit_log_filter_options(session)


@router.get("/", response_model=AuditLogPagedResponse)
async def api_list_audit_logs(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    module_name: Optional[str] = Query(None),
    table_name: Optional[str] = Query(None),
    record_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    performed_by_user_id: Optional[int] = Query(None),
    performed_by_name: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """List audit logs with optional filters and pagination."""
    resolved_from, resolved_to = _resolve_date_range(
        start_date, end_date, date_from, date_to
    )
    return await fetch_audit_logs(
        session,
        page=page,
        limit=limit,
        module_name=module_name,
        table_name=table_name,
        record_id=record_id,
        action=action,
        performed_by_user_id=performed_by_user_id,
        performed_by_name=performed_by_name,
        date_from=resolved_from,
        date_to=resolved_to,
        search=search,
    )


@router.get("/{audit_log_id}", response_model=AuditLogDetail)
async def api_get_audit_log(
    audit_log_id: int,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Return a single audit log with full old/new data."""
    return await fetch_audit_log_detail(session, audit_log_id)
