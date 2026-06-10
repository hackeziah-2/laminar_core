from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.audit_log import (
    enrich_audit_log_reads,
    get_audit_log_by_id,
    get_audit_log_filter_options,
    get_audit_log_summary,
    list_audit_logs,
)
from app.schemas.audit_log_schema import (
    AuditLogDetail,
    AuditLogFilterOptions,
    AuditLogPagedResponse,
    AuditLogRead,
    AuditLogSummary,
)


async def fetch_audit_logs(
    session: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    module_name: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[str] = None,
    performed_by_user_id: Optional[int] = None,
    performed_by_name: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
) -> AuditLogPagedResponse:
    """List audit logs with pagination, filters, and summary counts."""
    offset = (page - 1) * limit
    filter_kwargs = {
        "module_name": module_name,
        "table_name": table_name,
        "record_id": record_id,
        "action": action,
        "performed_by_user_id": performed_by_user_id,
        "performed_by_name": performed_by_name,
        "date_from": date_from,
        "date_to": date_to,
        "search": search,
    }

    items, total = await list_audit_logs(
        session,
        limit=limit,
        offset=offset,
        **filter_kwargs,
    )
    summary = await get_audit_log_summary(session, **filter_kwargs)

    return AuditLogPagedResponse(
        page=page,
        limit=limit,
        total=total,
        summary=summary,
        items=items,
    )


async def fetch_audit_log_detail(
    session: AsyncSession,
    audit_log_id: int,
) -> AuditLogDetail:
    """Return a single audit log or raise 404."""
    row = await get_audit_log_by_id(session, audit_log_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit log not found")
    enriched = await enrich_audit_log_reads(
        session,
        [AuditLogRead.from_orm(row)],
    )
    return AuditLogDetail(**enriched[0].dict())


async def fetch_audit_log_filter_options(
    session: AsyncSession,
) -> AuditLogFilterOptions:
    """Return distinct values for audit log filter dropdowns."""
    modules, users = await get_audit_log_filter_options(session)
    return AuditLogFilterOptions(
        module_names=modules,
        performed_by_names=users,
    )


async def fetch_audit_logs_for_export(
    session: AsyncSession,
    *,
    module_name: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[str] = None,
    performed_by_user_id: Optional[int] = None,
    performed_by_name: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
    max_rows: int = 5000,
) -> Tuple[list[AuditLogRead], AuditLogSummary]:
    """Return up to max_rows audit logs for export."""
    filter_kwargs = {
        "module_name": module_name,
        "table_name": table_name,
        "record_id": record_id,
        "action": action,
        "performed_by_user_id": performed_by_user_id,
        "performed_by_name": performed_by_name,
        "date_from": date_from,
        "date_to": date_to,
        "search": search,
    }
    items, _ = await list_audit_logs(
        session,
        limit=max_rows,
        offset=0,
        **filter_kwargs,
    )
    summary = await get_audit_log_summary(session, **filter_kwargs)
    return items, summary
