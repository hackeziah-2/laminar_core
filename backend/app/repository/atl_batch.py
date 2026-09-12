from typing import List, Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.atl_batch import AtlBatch
from app.models.audit_log import AuditAction
from app.schemas.atl_batch_schema import (
    AtlBatchCreate,
    AtlBatchRead,
    AtlBatchUpdate,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


async def _ensure_aircraft_exists(
    session: AsyncSession, aircraft_id: Optional[int]
) -> None:
    if aircraft_id is None:
        return
    result = await session.execute(
        select(Aircraft.id).where(
            Aircraft.id == aircraft_id,
            Aircraft.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="Aircraft not found")


async def _name_taken(
    session: AsyncSession,
    name: str,
    aircraft_id: Optional[int],
    *,
    exclude_id: Optional[int] = None,
) -> bool:
    stmt = select(AtlBatch).where(
        AtlBatch.name == name,
        AtlBatch.is_deleted.is_(False),
    )
    if aircraft_id is None:
        stmt = stmt.where(AtlBatch.aircraft_id.is_(None))
    else:
        stmt = stmt.where(AtlBatch.aircraft_id == aircraft_id)
    if exclude_id is not None:
        stmt = stmt.where(AtlBatch.id != exclude_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


def _batch_stmt():
    return select(AtlBatch).options(selectinload(AtlBatch.aircraft))


async def create_atl_batch(
    session: AsyncSession,
    data: AtlBatchCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AtlBatchRead:
    await _ensure_aircraft_exists(session, data.aircraft_id)
    if await _name_taken(session, data.name, data.aircraft_id):
        raise HTTPException(
            status_code=400,
            detail="ATL batch with this name already exists",
        )
    payload = data.dict() if hasattr(data, "dict") else data.model_dump()
    obj = AtlBatch(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)

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

    return AtlBatchRead.from_orm(obj)


async def get_atl_batch(session: AsyncSession, batch_id: int) -> Optional[AtlBatchRead]:
    result = await session.execute(
        _batch_stmt().where(
            AtlBatch.id == batch_id,
            AtlBatch.is_deleted.is_(False),
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AtlBatchRead.from_orm(obj)


async def update_atl_batch(
    session: AsyncSession,
    batch_id: int,
    data: AtlBatchUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[AtlBatchRead]:
    obj = await session.get(AtlBatch, batch_id)
    if not obj or obj.is_deleted:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = (
        data.dict(exclude_unset=True)
        if hasattr(data, "dict")
        else data.model_dump(exclude_unset=True)
    )
    next_name = update_data.get("name", obj.name)
    next_aircraft_id = update_data.get("aircraft_id", obj.aircraft_id)
    if "aircraft_id" in update_data:
        await _ensure_aircraft_exists(session, next_aircraft_id)
    if await _name_taken(
        session, next_name, next_aircraft_id, exclude_id=batch_id
    ):
        raise HTTPException(
            status_code=400,
            detail="ATL batch with this name already exists",
        )
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)

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

    return AtlBatchRead.from_orm(obj)


async def list_atl_batches_paged(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
    aircraft_id: Optional[int] = None,
) -> Tuple[List[AtlBatch], int]:
    stmt = _batch_stmt().where(AtlBatch.is_deleted.is_(False))
    count_stmt = select(func.count()).select_from(AtlBatch).where(
        AtlBatch.is_deleted.is_(False)
    )
    if aircraft_id is not None:
        stmt = stmt.where(AtlBatch.aircraft_id == aircraft_id)
        count_stmt = count_stmt.where(AtlBatch.aircraft_id == aircraft_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        search_filter = (AtlBatch.name.ilike(q)) | (AtlBatch.description.ilike(q))
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    sortable = {
        "id": AtlBatch.id,
        "name": AtlBatch.name,
        "aircraft_id": AtlBatch.aircraft_id,
        "created_at": AtlBatch.created_at,
        "updated_at": AtlBatch.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AtlBatch.name.asc())

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_atl_batches_list(
    session: AsyncSession,
    aircraft_id: Optional[int] = None,
) -> List[AtlBatch]:
    stmt = (
        select(AtlBatch)
        .where(AtlBatch.is_deleted.is_(False))
        .order_by(AtlBatch.created_at.desc(), AtlBatch.id.desc())
    )
    if aircraft_id is not None:
        stmt = stmt.where(AtlBatch.aircraft_id == aircraft_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def soft_delete_atl_batch(
    session: AsyncSession,
    batch_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    obj = await session.get(AtlBatch, batch_id)
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
            record_id=batch_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
