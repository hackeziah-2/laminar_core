from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import cast, func, or_, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.models.audit_log import AuditAction, AuditLog
from app.schemas.audit_log_schema import AuditLogRead, AuditLogSummary

_AUDIT_ACCOUNT_FIELDS = ("created_by", "updated_by")


def _collect_account_ids_from_data(data: Optional[Dict[str, Any]]) -> Set[int]:
    ids: Set[int] = set()
    if not isinstance(data, dict):
        return ids
    for field in _AUDIT_ACCOUNT_FIELDS:
        value = data.get(field)
        if isinstance(value, int):
            ids.add(value)
    return ids


def _collect_account_ids_from_audit_reads(items: List[AuditLogRead]) -> Set[int]:
    ids: Set[int] = set()
    for item in items:
        ids.update(_collect_account_ids_from_data(item.old_data))
        ids.update(_collect_account_ids_from_data(item.new_data))
    return ids


async def _fetch_account_name_map(
    session: AsyncSession,
    account_ids: Set[int],
) -> Dict[int, str]:
    if not account_ids:
        return {}
    result = await session.execute(
        select(AccountInformation).where(AccountInformation.id.in_(account_ids))
    )
    return {
        account.id: account.full_name
        for account in result.scalars().all()
        if account.full_name
    }


def _resolve_account_fields_in_data(
    data: Optional[Dict[str, Any]],
    name_map: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict):
        return data
    resolved = dict(data)
    for field in _AUDIT_ACCOUNT_FIELDS:
        value = resolved.get(field)
        if isinstance(value, int) and value in name_map:
            resolved[field] = name_map[value]
    return resolved


def _enrich_audit_log_read(
    item: AuditLogRead,
    name_map: Dict[int, str],
) -> AuditLogRead:
    return item.copy(
        update={
            "old_data": _resolve_account_fields_in_data(item.old_data, name_map),
            "new_data": _resolve_account_fields_in_data(item.new_data, name_map),
        }
    )


async def enrich_audit_log_reads(
    session: AsyncSession,
    items: List[AuditLogRead],
) -> List[AuditLogRead]:
    """Replace created_by/updated_by account IDs with full_name in old/new data."""
    if not items:
        return items
    name_map = await _fetch_account_name_map(
        session,
        _collect_account_ids_from_audit_reads(items),
    )
    if not name_map:
        return items
    return [_enrich_audit_log_read(item, name_map) for item in items]


def _build_audit_log_filters(
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
) -> list:
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
    if performed_by_name:
        filters.append(AuditLog.performed_by_name.ilike(f"%{performed_by_name}%"))
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                AuditLog.module_name.ilike(term),
                AuditLog.table_name.ilike(term),
                AuditLog.performed_by_name.ilike(term),
                AuditLog.action.ilike(term),
                cast(AuditLog.record_id, String).ilike(term),
                cast(AuditLog.id, String).ilike(term),
            )
        )

    return filters


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
    performed_by_name: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
) -> Tuple[List[AuditLogRead], int]:
    """Return paginated audit logs with optional filters, newest first."""
    filters = _build_audit_log_filters(
        module_name=module_name,
        table_name=table_name,
        record_id=record_id,
        action=action,
        performed_by_user_id=performed_by_user_id,
        performed_by_name=performed_by_name,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

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
    items = await enrich_audit_log_reads(session, items)
    return items, total


async def get_audit_log_by_id(
    session: AsyncSession,
    audit_log_id: int,
) -> Optional[AuditLog]:
    """Return a single audit log by primary key."""
    result = await session.execute(
        select(AuditLog).where(AuditLog.id == audit_log_id)
    )
    return result.scalar_one_or_none()


async def get_audit_log_summary(
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
) -> AuditLogSummary:
    """Return action counts for the current filter set."""
    filters = _build_audit_log_filters(
        module_name=module_name,
        table_name=table_name,
        record_id=record_id,
        action=action,
        performed_by_user_id=performed_by_user_id,
        performed_by_name=performed_by_name,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

    stmt = select(AuditLog.action, func.count()).select_from(AuditLog)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.group_by(AuditLog.action)

    result = await session.execute(stmt)
    counts = {row[0]: row[1] for row in result.all()}

    total = sum(counts.values())
    return AuditLogSummary(
        total=total,
        creates=counts.get(AuditAction.CREATE.value, 0),
        updates=counts.get(AuditAction.UPDATE.value, 0),
        deletes=counts.get(AuditAction.DELETE.value, 0),
    )


async def get_audit_log_filter_options(
    session: AsyncSession,
) -> Tuple[List[str], List[str]]:
    """Return distinct module names and performer names for filter dropdowns."""
    module_result = await session.execute(
        select(AuditLog.module_name)
        .distinct()
        .order_by(AuditLog.module_name.asc())
    )
    user_result = await session.execute(
        select(AuditLog.performed_by_name)
        .where(AuditLog.performed_by_name.isnot(None))
        .distinct()
        .order_by(AuditLog.performed_by_name.asc())
    )
    modules = [row[0] for row in module_result.all() if row[0]]
    users = [row[0] for row in user_result.all() if row[0]]
    return modules, users
