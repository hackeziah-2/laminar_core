from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oem_item_type import OemItemType
from app.schemas.oem_item_type_schema import (
    OemItemTypeCreate,
    OemItemTypeUpdate,
    OemItemTypeRead,
)


async def create_oem_item_type(
    session: AsyncSession,
    data: OemItemTypeCreate,
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
    await session.commit()
    await session.refresh(obj)
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
) -> Optional[OemItemTypeRead]:
    """Update an OEM Item Type."""
    obj = await session.get(OemItemType, item_type_id)
    if not obj or obj.is_deleted:
        return None
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
    await session.commit()
    await session.refresh(obj)
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
) -> bool:
    """Soft delete an OEM Item Type."""
    obj = await session.get(OemItemType, item_type_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
