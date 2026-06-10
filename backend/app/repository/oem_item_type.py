from typing import Optional, List, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.oem_item_type import OemItemType
from app.schemas.oem_item_type_schema import (
    OemItemTypeCreate,
    OemItemTypeUpdate,
    OemItemTypeRead,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


async def create_oem_item_type(
    session: AsyncSession,
    data: OemItemTypeCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> OemItemTypeRead:
    """Create a new OEM Item Type."""
    result = await session.execute(
        select(OemItemType).where(
            OemItemType.name == data.name,
            OemItemType.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="OEM item type with this name already exists",
        )
    obj = OemItemType(**data.dict())
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

    return OemItemTypeRead.from_orm(obj)


async def get_oem_item_type(
    session: AsyncSession,
    item_type_id: int,
) -> Optional[OemItemTypeRead]:
    """Get an OEM Item Type by ID."""
    result = await session.execute(
        select(OemItemType)
        .where(OemItemType.id == item_type_id)
        .where(OemItemType.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return OemItemTypeRead.from_orm(obj)


async def update_oem_item_type(
    session: AsyncSession,
    item_type_id: int,
    data: OemItemTypeUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[OemItemTypeRead]:
    """Update an OEM Item Type."""
    obj = await session.get(OemItemType, item_type_id)
    if not obj or obj.is_deleted:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(OemItemType).where(
                OemItemType.name == update_data["name"],
                OemItemType.id != item_type_id,
                OemItemType.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="OEM item type with this name already exists",
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

    return OemItemTypeRead.from_orm(obj)


async def list_oem_item_types(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[OemItemType], int]:
    """List OEM Item Types with pagination."""
    stmt = (
        select(OemItemType)
        .where(OemItemType.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(OemItemType.name.ilike(q))

    sortable = {
        "id": OemItemType.id,
        "name": OemItemType.name,
        "created_at": OemItemType.created_at,
        "updated_at": OemItemType.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(OemItemType.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(OemItemType)
        .where(OemItemType.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(OemItemType.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_oem_item_types_list(
    session: AsyncSession,
) -> List[OemItemType]:
    """Get all (no pagination, for dropdowns)."""
    result = await session.execute(
        select(OemItemType)
        .where(OemItemType.is_deleted == False)
        .order_by(OemItemType.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_oem_item_type(
    session: AsyncSession,
    item_type_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete an OEM Item Type."""
    obj = await session.get(OemItemType, item_type_id)
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
            record_id=item_type_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
