"""Persistence helpers for generic Excel import."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from app.database import set_audit_fields
from app.models.aircraft import Aircraft
from app.models.fleet_daily_update import FleetDailyUpdate, FleetDailyUpdateStatusEnum
from app.services.excel_import.hooks.base import ImportHook


def model_column_names(model: type) -> set:
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


def normalize_unique_fields(unique_fields: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(unique_fields, str):
        return [unique_fields]
    return list(unique_fields)


def validated_to_dict(validated: BaseModel) -> Dict[str, Any]:
    if hasattr(validated, "model_dump"):
        return validated.model_dump()
    return validated.dict()


async def find_by_unique_fields(
    session: AsyncSession,
    model: type,
    validated: BaseModel,
    fields: List[str],
    *,
    exclude_id: Optional[int] = None,
) -> Optional[Any]:
    stmt = select(model)
    for field in fields:
        stmt = stmt.where(getattr(model, field) == getattr(validated, field, None))
    if exclude_id is not None and hasattr(model, "id"):
        stmt = stmt.where(model.id != exclude_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_validated_row(
    session: AsyncSession,
    model: type,
    validated: BaseModel,
    fields: List[str],
    hook: ImportHook,
    *,
    audit_account_id: Optional[int] = None,
) -> tuple[Any, bool]:
    """
    Insert or update one row. Returns (entity, created).
    Raises nothing on duplicate unique conflict — caller should check conflict first.
    """
    model_columns = model_column_names(model)
    existing = await find_by_unique_fields(session, model, validated, fields)

    data = validated_to_dict(validated)

    if existing:
        conflict = await find_by_unique_fields(
            session,
            model,
            validated,
            fields,
            exclude_id=getattr(existing, "id", None),
        )
        if conflict:
            raise ValueError("Duplicate unique field value")

        for key in model_columns:
            if key in data:
                setattr(existing, key, data[key])
        if hasattr(existing, "is_deleted") and existing.is_deleted:
            existing.is_deleted = False
        if audit_account_id is not None:
            await set_audit_fields(existing, audit_account_id, is_create=False)
        await hook.after_upsert(
            session,
            validated=validated,
            existing=existing,
            obj=existing,
            audit_account_id=audit_account_id,
        )
        return existing, False

    conflict = await find_by_unique_fields(session, model, validated, fields)
    if conflict:
        raise ValueError("Duplicate unique field value")

    payload = {k: data[k] for k in model_columns if k in data}
    obj = model(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    if not existing:
        await session.flush()
    await hook.after_upsert(
        session,
        validated=validated,
        existing=None,
        obj=obj,
        audit_account_id=audit_account_id,
    )
    return obj, True


async def sync_fleet_daily_updates_for_aircraft(
    session: AsyncSession,
    registrations: List[str],
    *,
    audit_account_id: Optional[int] = None,
) -> None:
    """Ensure fleet daily update rows exist and are OP for imported aircraft."""
    if not registrations:
        return

    result = await session.execute(
        select(Aircraft).where(Aircraft.registration.in_(registrations))
    )
    aircraft_list = result.scalars().all()

    for aircraft in aircraft_list:
        fd_result = await session.execute(
            select(FleetDailyUpdate).where(FleetDailyUpdate.aircraft_fk == aircraft.id)
        )
        fd_row = fd_result.scalar_one_or_none()

        if fd_row:
            fd_row.is_deleted = False
            fd_row.status = FleetDailyUpdateStatusEnum.OP.value
            if audit_account_id is not None:
                await set_audit_fields(fd_row, audit_account_id, is_create=False)
        else:
            fd_new = FleetDailyUpdate(
                aircraft_fk=aircraft.id,
                status=FleetDailyUpdateStatusEnum.OP.value,
            )
            session.add(fd_new)
            if audit_account_id is not None:
                await set_audit_fields(fd_new, audit_account_id, is_create=True)

    await session.commit()
