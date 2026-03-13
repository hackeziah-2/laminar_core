from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.authorization_scope_cessna import AuthorizationScopeCessna
from app.schemas.authorization_scope_cessna_schema import (
    AuthorizationScopeCessnaCreate,
    AuthorizationScopeCessnaUpdate,
    AuthorizationScopeCessnaRead,
)


async def create_authorization_scope_cessna(
    session: AsyncSession,
    data: AuthorizationScopeCessnaCreate,
) -> AuthorizationScopeCessnaRead:
    result = await session.execute(
        select(AuthorizationScopeCessna).where(
            AuthorizationScopeCessna.name == data.name,
            AuthorizationScopeCessna.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Authorization scope Cessna with this name already exists",
        )
    obj = AuthorizationScopeCessna(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return AuthorizationScopeCessnaRead.from_orm(obj)


async def get_authorization_scope_cessna(
    session: AsyncSession,
    scope_id: int,
) -> Optional[AuthorizationScopeCessnaRead]:
    result = await session.execute(
        select(AuthorizationScopeCessna)
        .where(AuthorizationScopeCessna.id == scope_id)
        .where(AuthorizationScopeCessna.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AuthorizationScopeCessnaRead.from_orm(obj)


async def update_authorization_scope_cessna(
    session: AsyncSession,
    scope_id: int,
    data: AuthorizationScopeCessnaUpdate,
) -> Optional[AuthorizationScopeCessnaRead]:
    obj = await session.get(AuthorizationScopeCessna, scope_id)
    if not obj or obj.is_deleted:
        return None
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(AuthorizationScopeCessna).where(
                AuthorizationScopeCessna.name == update_data["name"],
                AuthorizationScopeCessna.id != scope_id,
                AuthorizationScopeCessna.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Authorization scope Cessna with this name already exists",
            )
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return AuthorizationScopeCessnaRead.from_orm(obj)


async def list_authorization_scope_cessna(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[AuthorizationScopeCessna], int]:
    stmt = select(AuthorizationScopeCessna).where(
        AuthorizationScopeCessna.is_deleted == False
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(AuthorizationScopeCessna.name.ilike(q))

    sortable = {
        "id": AuthorizationScopeCessna.id,
        "name": AuthorizationScopeCessna.name,
        "created_at": AuthorizationScopeCessna.created_at,
        "updated_at": AuthorizationScopeCessna.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AuthorizationScopeCessna.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(AuthorizationScopeCessna)
        .where(AuthorizationScopeCessna.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(AuthorizationScopeCessna.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_authorization_scope_cessna_list(
    session: AsyncSession,
) -> List[AuthorizationScopeCessna]:
    result = await session.execute(
        select(AuthorizationScopeCessna)
        .where(AuthorizationScopeCessna.is_deleted == False)
        .order_by(AuthorizationScopeCessna.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_authorization_scope_cessna(
    session: AsyncSession,
    scope_id: int,
) -> bool:
    obj = await session.get(AuthorizationScopeCessna, scope_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
