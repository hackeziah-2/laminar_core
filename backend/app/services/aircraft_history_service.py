import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import active_query, set_audit_fields
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.aircraft_history import AircraftHistory
from app.models.audit_log import AuditAction
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.repository.aircraft import _persist_upload_file
from app.schemas.aircraft_history_schema import (
    AircraftHistoryRead,
    AircraftUpdateWithHistoryResponse,
)
from app.schemas.aircraft_schema import AircraftOut, AircraftUpdate


def _normalize_comparable_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_history_value(value: Any) -> Optional[str]:
    normalized = _normalize_comparable_value(value)
    if normalized is None:
        return None
    if isinstance(normalized, (str, int, float, bool)):
        return str(normalized)
    return json.dumps(normalized, default=str, sort_keys=True)


def track_changes(old_data: Dict[str, Any], new_data: Dict[str, Any], user_id: Optional[int]) -> list[Dict[str, Any]]:
    changes: list[Dict[str, Any]] = []

    for field_name, new_value in new_data.items():
        old_value = old_data.get(field_name)
        if _normalize_comparable_value(old_value) == _normalize_comparable_value(new_value):
            continue

        changes.append(
            {
                "field_name": field_name,
                "old_value": _serialize_history_value(old_value),
                "new_value": _serialize_history_value(new_value),
                "changed_by": user_id,
            }
        )

    return changes


async def list_aircraft_history(
    session: AsyncSession,
    aircraft_id: int,
) -> list[AircraftHistoryRead]:
    result = await session.execute(
        select(AircraftHistory)
        .where(AircraftHistory.aircraft_id == aircraft_id)
        .options(selectinload(AircraftHistory.changed_by_user))
        .order_by(AircraftHistory.changed_at.desc(), AircraftHistory.id.desc())
    )
    return [AircraftHistoryRead.from_orm(item) for item in result.scalars().all()]


async def list_aircraft_history_paged(
    session: AsyncSession,
    aircraft_id: int,
    *,
    limit: int,
    offset: int,
) -> Tuple[list[AircraftHistoryRead], int]:
    count_result = await session.execute(
        select(func.count())
        .select_from(AircraftHistory)
        .where(AircraftHistory.aircraft_id == aircraft_id)
    )
    total = count_result.scalar() or 0

    result = await session.execute(
        select(AircraftHistory)
        .where(AircraftHistory.aircraft_id == aircraft_id)
        .options(selectinload(AircraftHistory.changed_by_user))
        .order_by(AircraftHistory.changed_at.desc(), AircraftHistory.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [AircraftHistoryRead.from_orm(item) for item in result.scalars().all()]
    return items, total


async def _validate_unique_fields(
    session: AsyncSession,
    aircraft_id: int,
    update_data: Dict[str, Any],
) -> None:
    if "registration" in update_data:
        result = await session.execute(
            active_query(Aircraft).where(
                Aircraft.registration == update_data["registration"],
                Aircraft.id != aircraft_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Registration already exists")

    if "msn" in update_data:
        result = await session.execute(
            active_query(Aircraft).where(
                Aircraft.msn == update_data["msn"],
                Aircraft.id != aircraft_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="MSN already exists")


def _extract_old_values(aircraft: Aircraft, fields: Iterable[str]) -> Dict[str, Any]:
    return {field_name: getattr(aircraft, field_name, None) for field_name in fields}


async def update_aircraft_with_history(
    session: AsyncSession,
    aircraft_id: int,
    data: AircraftUpdate,
    user_id: Optional[int],
    *,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AircraftUpdateWithHistoryResponse:
    result = await session.execute(select(Aircraft).where(Aircraft.id == aircraft_id))
    aircraft = result.scalar_one_or_none()

    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    update_data = data.dict(exclude_unset=True)

    if engine_file:
        update_data["engine_arc"] = await _persist_upload_file(engine_file)

    if propeller_file:
        update_data["propeller_arc"] = await _persist_upload_file(propeller_file)

    await _validate_unique_fields(session, aircraft_id, update_data)

    old_data_snapshot = serialize_audit_data(aircraft)
    old_data = _extract_old_values(aircraft, update_data.keys())
    changes = track_changes(old_data, update_data, user_id)

    if not changes:
        await session.refresh(aircraft)
        return AircraftUpdateWithHistoryResponse(
            aircraft=AircraftOut.from_orm(aircraft),
            history_records=[],
        )

    for key, value in update_data.items():
        setattr(aircraft, key, value)

    if user_id is not None:
        await set_audit_fields(aircraft, user_id, is_create=False)

    history_rows = []
    for change in changes:
        history = AircraftHistory(
            aircraft_id=aircraft.id,
            field_name=change["field_name"],
            old_value=change["old_value"],
            new_value=change["new_value"],
            changed_by=change["changed_by"],
            action_type="UPDATE",
        )
        session.add(history)
        history_rows.append(history)

    session.add(aircraft)
    await session.commit()
    await session.refresh(aircraft)

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=aircraft.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=aircraft,
            current_user=audit_user,
            request=audit_request,
        )

    for history in history_rows:
        await session.refresh(history)

    return AircraftUpdateWithHistoryResponse(
        aircraft=AircraftOut.from_orm(aircraft),
        history_records=[AircraftHistoryRead.from_orm(item) for item in history_rows],
    )


async def update_aircraft_and_log_history(
    session: AsyncSession,
    aircraft_id: int,
    data: AircraftUpdate,
    user_id: Optional[int],
    *,
    engine_file: UploadFile = None,
    propeller_file: UploadFile = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AircraftOut:
    result = await update_aircraft_with_history(
        session=session,
        aircraft_id=aircraft_id,
        data=data,
        user_id=user_id,
        engine_file=engine_file,
        propeller_file=propeller_file,
        audit_module_name=audit_module_name,
        audit_table_name=audit_table_name,
        audit_user=audit_user,
        audit_request=audit_request,
    )
    return result.aircraft
