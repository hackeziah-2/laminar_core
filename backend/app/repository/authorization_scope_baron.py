from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.authorization_scope_baron import AuthorizationScopeBaron
from app.schemas.authorization_scope_baron_schema import (
    AuthorizationScopeBaronCreate,
    AuthorizationScopeBaronUpdate,
    AuthorizationScopeBaronRead,
)


async def create_authorization_scope_baron(
    session: AsyncSession,
    data: AuthorizationScopeBaronCreate,
) -> AuthorizationScopeBaronRead:
    result = await session.execute(
        select(AuthorizationScopeBaron).where(
            AuthorizationScopeBaron.name == data.name,
            AuthorizationScopeBaron.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Authorization scope Baron with this name already exists",
        )
    obj = AuthorizationScopeBaron(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return AuthorizationScopeBaronRead.from_orm(obj)


async def get_authorization_scope_baron(
    session: AsyncSession,
    scope_id: int,
) -> Optional[AuthorizationScopeBaronRead]:
    result = await session.execute(
        select(AuthorizationScopeBaron)
        .where(AuthorizationScopeBaron.id == scope_id)
        .where(AuthorizationScopeBaron.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AuthorizationScopeBaronRead.from_orm(obj)


async def update_authorization_scope_baron(
    session: AsyncSession,
    scope_id: int,
    data: AuthorizationScopeBaronUpdate,
) -> Optional[AuthorizationScopeBaronRead]:
    obj = await session.get(AuthorizationScopeBaron, scope_id)
    if not obj or obj.is_deleted:
        return None
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(AuthorizationScopeBaron).where(
                AuthorizationScopeBaron.name == update_data["name"],
                AuthorizationScopeBaron.id != scope_id,
                AuthorizationScopeBaron.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Authorization scope Baron with this name already exists",
            )
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return AuthorizationScopeBaronRead.from_orm(obj)


async def list_authorization_scope_baron(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[AuthorizationScopeBaron], int]:
    stmt = select(AuthorizationScopeBaron).where(
        AuthorizationScopeBaron.is_deleted == False
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(AuthorizationScopeBaron.name.ilike(q))

    sortable = {
        "id": AuthorizationScopeBaron.id,
        "name": AuthorizationScopeBaron.name,
        "created_at": AuthorizationScopeBaron.created_at,
        "updated_at": AuthorizationScopeBaron.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AuthorizationScopeBaron.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(AuthorizationScopeBaron)
        .where(AuthorizationScopeBaron.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(AuthorizationScopeBaron.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_authorization_scope_baron_list(
    session: AsyncSession,
) -> List[AuthorizationScopeBaron]:
    result = await session.execute(
        select(AuthorizationScopeBaron)
        .where(AuthorizationScopeBaron.is_deleted == False)
        .order_by(AuthorizationScopeBaron.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_authorization_scope_baron(
    session: AsyncSession,
    scope_id: int,
) -> bool:
    obj = await session.get(AuthorizationScopeBaron, scope_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
