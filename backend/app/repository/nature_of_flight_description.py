from typing import List, Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import TypeEnum
from app.models.audit_log import AuditAction
from app.models.nature_of_flight_description import NatureOfFlightDescription
from app.schemas.nature_of_flight_description_schema import (
    NatureOfFlightDescriptionCreate,
    NatureOfFlightDescriptionRead,
    NatureOfFlightDescriptionUpdate,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


def _normalize_nature_of_flight(value) -> Optional[TypeEnum]:
    if value is None:
        return None
    if isinstance(value, TypeEnum):
        return value
    if isinstance(value, str) and value.strip():
        key = value.strip().upper().replace(" ", "_")
        try:
            return TypeEnum(key)
        except ValueError:
            return None
    return None


async def _existing_for_aircraft_and_nature(
    session: AsyncSession,
    aircraft_fk: int,
    nature_of_flight: TypeEnum,
    *,
    exclude_id: Optional[int] = None,
) -> Optional[NatureOfFlightDescription]:
    stmt = (
        select(NatureOfFlightDescription)
        .where(NatureOfFlightDescription.aircraft_fk == aircraft_fk)
        .where(NatureOfFlightDescription.nature_of_flight == nature_of_flight)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    if exclude_id is not None:
        stmt = stmt.where(NatureOfFlightDescription.id != exclude_id)
    result = await session.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def create_nature_of_flight_description(
    session: AsyncSession,
    data: NatureOfFlightDescriptionCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> NatureOfFlightDescriptionRead:
    """Create a Nature of Flight Description entry."""
    payload = data.dict()
    nf = _normalize_nature_of_flight(payload.get("nature_of_flight"))
    if nf is None:
        raise HTTPException(status_code=422, detail="Invalid nature_of_flight")
    payload["nature_of_flight"] = nf

    if await _existing_for_aircraft_and_nature(
        session, payload["aircraft_fk"], nf
    ):
        raise HTTPException(
            status_code=409,
            detail="Nature of Flight Description already exists for this aircraft and nature_of_flight",
        )

    obj = NatureOfFlightDescription(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return NatureOfFlightDescriptionRead.from_orm(obj)


async def get_nature_of_flight_description(
    session: AsyncSession,
    entry_id: int,
) -> Optional[NatureOfFlightDescription]:
    """Get a Nature of Flight Description by ID."""
    result = await session.execute(
        select(NatureOfFlightDescription)
        .options(selectinload(NatureOfFlightDescription.aircraft))
        .where(NatureOfFlightDescription.id == entry_id)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_nature_of_flight_description_by_aircraft(
    session: AsyncSession,
    entry_id: int,
    aircraft_fk: int,
) -> Optional[NatureOfFlightDescription]:
    """Get a Nature of Flight Description by ID scoped to aircraft."""
    result = await session.execute(
        select(NatureOfFlightDescription)
        .options(selectinload(NatureOfFlightDescription.aircraft))
        .where(NatureOfFlightDescription.id == entry_id)
        .where(NatureOfFlightDescription.aircraft_fk == aircraft_fk)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_nature_of_flight_description_by_aircraft_and_nature(
    session: AsyncSession,
    aircraft_fk: int,
    nature_of_flight: TypeEnum,
) -> Optional[NatureOfFlightDescription]:
    """Get the active Nature of Flight Description for an aircraft and type."""
    return await _existing_for_aircraft_and_nature(
        session, aircraft_fk, nature_of_flight
    )


async def update_nature_of_flight_description(
    session: AsyncSession,
    entry_id: int,
    data: NatureOfFlightDescriptionUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[NatureOfFlightDescriptionRead]:
    """Update a Nature of Flight Description entry."""
    result = await session.execute(
        select(NatureOfFlightDescription)
        .options(selectinload(NatureOfFlightDescription.aircraft))
        .where(NatureOfFlightDescription.id == entry_id)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if "nature_of_flight" in update_data:
        nf = _normalize_nature_of_flight(update_data["nature_of_flight"])
        if nf is None:
            raise HTTPException(status_code=422, detail="Invalid nature_of_flight")
        update_data["nature_of_flight"] = nf

    next_aircraft_fk = update_data.get("aircraft_fk", obj.aircraft_fk)
    next_nature_of_flight = update_data.get("nature_of_flight", obj.nature_of_flight)
    if await _existing_for_aircraft_and_nature(
        session,
        next_aircraft_fk,
        next_nature_of_flight,
        exclude_id=obj.id,
    ):
        raise HTTPException(
            status_code=409,
            detail="Nature of Flight Description already exists for this aircraft and nature_of_flight",
        )

    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return NatureOfFlightDescriptionRead.from_orm(obj)


async def list_nature_of_flight_descriptions(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
    aircraft_fk: Optional[int] = None,
    nature_of_flight: Optional[str] = None,
) -> Tuple[List[NatureOfFlightDescription], int]:
    """List Nature of Flight Description entries with pagination."""
    stmt = (
        select(NatureOfFlightDescription)
        .options(selectinload(NatureOfFlightDescription.aircraft))
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    if aircraft_fk is not None:
        stmt = stmt.where(NatureOfFlightDescription.aircraft_fk == aircraft_fk)

    nf = _normalize_nature_of_flight(nature_of_flight)
    if nf is not None:
        stmt = stmt.where(NatureOfFlightDescription.nature_of_flight == nf)

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.outerjoin(
            Aircraft,
            NatureOfFlightDescription.aircraft_fk == Aircraft.id,
        )
        stmt = stmt.where(
            or_(
                NatureOfFlightDescription.remarks.ilike(q),
                NatureOfFlightDescription.action_taken.ilike(q),
                cast(NatureOfFlightDescription.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        ).distinct()

    sortable = {
        "id": NatureOfFlightDescription.id,
        "aircraft_fk": NatureOfFlightDescription.aircraft_fk,
        "nature_of_flight": NatureOfFlightDescription.nature_of_flight,
        "remarks": NatureOfFlightDescription.remarks,
        "action_taken": NatureOfFlightDescription.action_taken,
        "created_at": NatureOfFlightDescription.created_at,
        "updated_at": NatureOfFlightDescription.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(NatureOfFlightDescription.id.desc())

    count_stmt = (
        select(func.count())
        .select_from(NatureOfFlightDescription)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(NatureOfFlightDescription.aircraft_fk == aircraft_fk)
    if nf is not None:
        count_stmt = count_stmt.where(NatureOfFlightDescription.nature_of_flight == nf)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.outerjoin(
            Aircraft,
            NatureOfFlightDescription.aircraft_fk == Aircraft.id,
        )
        count_stmt = count_stmt.where(
            or_(
                NatureOfFlightDescription.remarks.ilike(q),
                NatureOfFlightDescription.action_taken.ilike(q),
                cast(NatureOfFlightDescription.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        )
    total = (await session.execute(count_stmt)).scalar()
    if limit:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def soft_delete_nature_of_flight_description(
    session: AsyncSession,
    entry_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a Nature of Flight Description entry."""
    obj = await session.get(NatureOfFlightDescription, entry_id)
    if not obj or obj.is_deleted:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=entry_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def soft_delete_nature_of_flight_description_by_aircraft(
    session: AsyncSession,
    entry_id: int,
    aircraft_fk: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a Nature of Flight Description entry scoped to aircraft."""
    result = await session.execute(
        select(NatureOfFlightDescription)
        .where(NatureOfFlightDescription.id == entry_id)
        .where(NatureOfFlightDescription.aircraft_fk == aircraft_fk)
        .where(NatureOfFlightDescription.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=entry_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
