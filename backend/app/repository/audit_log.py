from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.audit_log_schema import AuditLogRead


async def list_audit_logs(
    session: AsyncSession,
    *,
    limit: int = 10,
    offset: int = 0,
    module_name: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[str] = None,
    performed_by_user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Tuple[List[AuditLogRead], int]:
    """Return paginated audit logs with optional filters."""
    filters = []

    if module_name:
        filters.append(AuditLog.module_name == module_name)
    if table_name:
        filters.append(AuditLog.table_name == table_name)
    if record_id is not None:
        filters.append(AuditLog.record_id == record_id)
    if action:
        filters.append(AuditLog.action == action)
    if performed_by_user_id is not None:
        filters.append(AuditLog.performed_by_user_id == performed_by_user_id)
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)

    count_stmt = select(func.count()).select_from(AuditLog)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = [AuditLogRead.from_orm(row) for row in result.scalars().all()]
    return items, total
