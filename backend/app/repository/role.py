from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role
from app.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
)


async def create_role(
    session: AsyncSession,
    data: RoleCreate
) -> RoleRead:
    """Create a new Role."""
    result = await session.execute(
        select(Role).where(
            Role.name == data.name,
            Role.is_deleted == False
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Role with this name already exists"
        )

    role = Role(**data.dict())
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return RoleRead.from_orm(role)


async def get_role(
    session: AsyncSession,
    role_id: int
) -> Optional[RoleRead]:
    """Get a Role by ID."""
    result = await session.execute(
        select(Role)
        .where(Role.id == role_id)
        .where(Role.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return RoleRead.from_orm(obj)


async def update_role(
    session: AsyncSession,
    role_id: int,
    role_in: RoleUpdate
) -> Optional[RoleRead]:
    """Update a Role."""
    obj = await session.get(Role, role_id)
    if not obj or obj.is_deleted:
        return None

    update_data = role_in.dict(exclude_unset=True)

    if "name" in update_data:
        result = await session.execute(
            select(Role).where(
                Role.name == update_data["name"],
                Role.id != role_id,
                Role.is_deleted == False
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Role with this name already exists"
            )

    for k, v in update_data.items():
        setattr(obj, k, v)

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return RoleRead.from_orm(obj)


async def list_roles(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[Role], int]:
    """List Roles with pagination."""
    stmt = (
        select(Role)
        .where(Role.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                Role.name.ilike(q),
                Role.description.ilike(q),
            )
        )

    sortable_fields = {
        "id": Role.id,
        "name": Role.name,
        "created_at": Role.created_at,
        "updated_at": Role.updated_at,
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
        stmt = stmt.order_by(Role.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(Role)
        .where(Role.is_deleted == False)
    )
    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                Role.name.ilike(q),
                Role.description.ilike(q),
            )
        )
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_roles_list(
    session: AsyncSession,
) -> List[Role]:
    """Get all Roles (no pagination, for dropdowns)."""
    result = await session.execute(
        select(Role)
        .where(Role.is_deleted == False)
        .order_by(Role.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_role(
    session: AsyncSession,
    role_id: int
) -> bool:
    """Soft delete a Role."""
    obj = await session.get(Role, role_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
