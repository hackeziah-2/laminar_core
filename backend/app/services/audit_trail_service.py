"""Reusable audit trail service for CRUD modules."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from app.models.account import AccountInformation
from app.models.audit_log import AuditAction, AuditLog


def _normalize_comparable_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize_audit_value(value: Any) -> Any:
    """Serialize a single value for JSON audit storage."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize_audit_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_audit_value(item) for item in value]
    return str(value)


def serialize_audit_data(data: Any) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """Serialize ORM model, dict, list, or Pydantic model for audit storage."""
    if data is None:
        return None
    if isinstance(data, dict):
        return {key: serialize_audit_value(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [serialize_audit_data(item) for item in data]
    if hasattr(data, "dict") and callable(data.dict):
        return serialize_audit_data(data.dict())
    if hasattr(data, "__table__"):
        mapper = sa_inspect(data.__class__)
        return {
            column.key: serialize_audit_value(getattr(data, column.key))
            for column in mapper.columns
        }
    return serialize_audit_value(data)


def detect_changed_fields(
    old_data: Optional[Dict[str, Any]],
    new_data: Optional[Dict[str, Any]],
) -> Optional[List[str]]:
    """Return field names whose values differ between old and new snapshots."""
    if not old_data or not new_data:
        return None

    changed: List[str] = []
    all_keys = set(old_data.keys()) | set(new_data.keys())
    for field_name in sorted(all_keys):
        old_value = _normalize_comparable_value(old_data.get(field_name))
        new_value = _normalize_comparable_value(new_data.get(field_name))
        if old_value != new_value:
            changed.append(field_name)
    return changed or None


def extract_request_metadata(
    request: Optional[Request],
) -> Tuple[Optional[str], Optional[str]]:
    """Extract client IP and user agent from a FastAPI request."""
    if request is None:
        return None, None

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client is not None:
        ip_address = request.client.host
    else:
        ip_address = None

    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


def _resolve_action(action: Union[AuditAction, str]) -> str:
    if isinstance(action, AuditAction):
        return action.value
    return str(action)


async def create_audit_log(
    db: AsyncSession,
    module_name: str,
    table_name: str,
    record_id: int,
    action: Union[AuditAction, str],
    old_data: Any,
    new_data: Any,
    current_user: Optional[AccountInformation],
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Persist an audit log entry. Call only after the primary operation commits successfully.
    """
    serialized_old = serialize_audit_data(old_data)
    serialized_new = serialize_audit_data(new_data)
    action_value = _resolve_action(action)

    changed_fields: Optional[List[str]] = None
    if action_value in {AuditAction.UPDATE.value, AuditAction.BULK_UPDATE.value}:
        if isinstance(serialized_old, dict) and isinstance(serialized_new, dict):
            changed_fields = detect_changed_fields(serialized_old, serialized_new)
        elif action_value == AuditAction.BULK_UPDATE.value:
            changed_fields = None

    ip_address, user_agent = extract_request_metadata(request)

    audit_log = AuditLog(
        module_name=module_name,
        table_name=table_name,
        record_id=record_id,
        action=action_value,
        old_data=serialized_old,
        new_data=serialized_new,
        changed_fields=changed_fields,
        performed_by_user_id=current_user.id if current_user is not None else None,
        performed_by_name=current_user.full_name if current_user is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)
    return audit_log
