from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module
from app.schemas.module_schema import (
    ModuleCreate,
    ModuleUpdate,
    ModuleRead,
)


async def create_module(
    session: AsyncSession,
    data: ModuleCreate
) -> ModuleRead:
    """Create a new Module."""
    result = await session.execute(
        select(Module).where(
            Module.name == data.name,
            Module.is_deleted == False
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Module with this name already exists"
        )

    module = Module(**data.dict())
    session.add(module)
    await session.commit()
    await session.refresh(module)
    return ModuleRead.from_orm(module)


async def get_module(
    session: AsyncSession,
    module_id: int
) -> Optional[ModuleRead]:
    """Get a Module by ID."""
    result = await session.execute(
        select(Module)
        .where(Module.id == module_id)
        .where(Module.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return ModuleRead.from_orm(obj)


async def update_module(
    session: AsyncSession,
    module_id: int,
    module_in: ModuleUpdate
) -> Optional[ModuleRead]:
    """Update a Module."""
    obj = await session.get(Module, module_id)
    if not obj or obj.is_deleted:
        return None

    update_data = module_in.dict(exclude_unset=True)

    if "name" in update_data:
        result = await session.execute(
            select(Module).where(
                Module.name == update_data["name"],
                Module.id != module_id,
                Module.is_deleted == False
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Module with this name already exists"
            )

    for k, v in update_data.items():
        setattr(obj, k, v)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return ModuleRead.from_orm(obj)


async def list_modules(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[Module], int]:
    """List Modules with pagination."""
    stmt = (
        select(Module)
        .where(Module.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        stmt = stmt.where(Module.name.ilike(q))

    sortable_fields = {
        "id": Module.id,
        "name": Module.name,
        "created_at": Module.created_at,
        "updated_at": Module.updated_at,
    }

    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")
            column = sortable_fields.get(field_name)
            if column is not None:
                stmt = stmt.order_by(
                    column.desc() if desc_order else column.asc()
                )
    else:
        stmt = stmt.order_by(Module.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(Module)
        .where(Module.is_deleted == False)
    )
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(Module.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_modules_list(
    session: AsyncSession,
) -> List[Module]:
    """Get all Modules (no pagination, for dropdowns)."""
    result = await session.execute(
        select(Module)
        .where(Module.is_deleted == False)
        .order_by(Module.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_module(
    session: AsyncSession,
    module_id: int
) -> bool:
    """Soft delete a Module."""
    obj = await session.get(Module, module_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
