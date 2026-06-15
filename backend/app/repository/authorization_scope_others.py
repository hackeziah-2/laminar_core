from typing import Optional, List, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.authorization_scope_others import AuthorizationScopeOthers
from app.schemas.authorization_scope_others_schema import (
    AuthorizationScopeOthersCreate,
    AuthorizationScopeOthersUpdate,
    AuthorizationScopeOthersRead,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


async def create_authorization_scope_others(
    session: AsyncSession,
    data: AuthorizationScopeOthersCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AuthorizationScopeOthersRead:
    result = await session.execute(
        select(AuthorizationScopeOthers).where(
            AuthorizationScopeOthers.name == data.name,
            AuthorizationScopeOthers.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Authorization scope (others) with this name already exists",
        )
    obj = AuthorizationScopeOthers(**data.dict())
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

    return AuthorizationScopeOthersRead.from_orm(obj)


async def get_authorization_scope_others(
    session: AsyncSession,
    scope_id: int,
) -> Optional[AuthorizationScopeOthersRead]:
    result = await session.execute(
        select(AuthorizationScopeOthers)
        .where(AuthorizationScopeOthers.id == scope_id)
        .where(AuthorizationScopeOthers.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AuthorizationScopeOthersRead.from_orm(obj)


async def update_authorization_scope_others(
    session: AsyncSession,
    scope_id: int,
    data: AuthorizationScopeOthersUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[AuthorizationScopeOthersRead]:
    obj = await session.get(AuthorizationScopeOthers, scope_id)
    if not obj or obj.is_deleted:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(AuthorizationScopeOthers).where(
                AuthorizationScopeOthers.name == update_data["name"],
                AuthorizationScopeOthers.id != scope_id,
                AuthorizationScopeOthers.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Authorization scope (others) with this name already exists",
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

    return AuthorizationScopeOthersRead.from_orm(obj)


async def list_authorization_scope_others(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[AuthorizationScopeOthers], int]:
    stmt = select(AuthorizationScopeOthers).where(
        AuthorizationScopeOthers.is_deleted == False
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(AuthorizationScopeOthers.name.ilike(q))

    sortable = {
        "id": AuthorizationScopeOthers.id,
        "name": AuthorizationScopeOthers.name,
        "created_at": AuthorizationScopeOthers.created_at,
        "updated_at": AuthorizationScopeOthers.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AuthorizationScopeOthers.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(AuthorizationScopeOthers)
        .where(AuthorizationScopeOthers.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(AuthorizationScopeOthers.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_authorization_scope_others_list(
    session: AsyncSession,
) -> List[AuthorizationScopeOthers]:
    result = await session.execute(
        select(AuthorizationScopeOthers)
        .where(AuthorizationScopeOthers.is_deleted == False)
        .order_by(AuthorizationScopeOthers.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_authorization_scope_others(
    session: AsyncSession,
    scope_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    obj = await session.get(AuthorizationScopeOthers, scope_id)
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
            record_id=scope_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
