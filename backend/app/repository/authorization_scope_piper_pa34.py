from typing import Optional, List, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.authorization_scope_piper_pa34 import AuthorizationScopePiperPa34
from app.schemas.authorization_scope_piper_pa34_schema import (
    AuthorizationScopePiperPa34Create,
    AuthorizationScopePiperPa34Update,
    AuthorizationScopePiperPa34Read,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


async def create_authorization_scope_piper_pa34(
    session: AsyncSession,
    data: AuthorizationScopePiperPa34Create,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AuthorizationScopePiperPa34Read:
    result = await session.execute(
        select(AuthorizationScopePiperPa34).where(
            AuthorizationScopePiperPa34.name == data.name,
            AuthorizationScopePiperPa34.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Authorization scope Piper PA-34 with this name already exists",
        )
    obj = AuthorizationScopePiperPa34(**data.dict())
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

    return AuthorizationScopePiperPa34Read.from_orm(obj)


async def get_authorization_scope_piper_pa34(
    session: AsyncSession,
    scope_id: int,
) -> Optional[AuthorizationScopePiperPa34Read]:
    result = await session.execute(
        select(AuthorizationScopePiperPa34)
        .where(AuthorizationScopePiperPa34.id == scope_id)
        .where(AuthorizationScopePiperPa34.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AuthorizationScopePiperPa34Read.from_orm(obj)


async def update_authorization_scope_piper_pa34(
    session: AsyncSession,
    scope_id: int,
    data: AuthorizationScopePiperPa34Update,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[AuthorizationScopePiperPa34Read]:
    obj = await session.get(AuthorizationScopePiperPa34, scope_id)
    if not obj or obj.is_deleted:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(AuthorizationScopePiperPa34).where(
                AuthorizationScopePiperPa34.name == update_data["name"],
                AuthorizationScopePiperPa34.id != scope_id,
                AuthorizationScopePiperPa34.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Authorization scope Piper PA-34 with this name already exists",
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

    return AuthorizationScopePiperPa34Read.from_orm(obj)


async def list_authorization_scope_piper_pa34(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[AuthorizationScopePiperPa34], int]:
    stmt = select(AuthorizationScopePiperPa34).where(
        AuthorizationScopePiperPa34.is_deleted == False
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(AuthorizationScopePiperPa34.name.ilike(q))

    sortable = {
        "id": AuthorizationScopePiperPa34.id,
        "name": AuthorizationScopePiperPa34.name,
        "created_at": AuthorizationScopePiperPa34.created_at,
        "updated_at": AuthorizationScopePiperPa34.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AuthorizationScopePiperPa34.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(AuthorizationScopePiperPa34)
        .where(AuthorizationScopePiperPa34.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(AuthorizationScopePiperPa34.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_authorization_scope_piper_pa34_list(
    session: AsyncSession,
) -> List[AuthorizationScopePiperPa34]:
    result = await session.execute(
        select(AuthorizationScopePiperPa34)
        .where(AuthorizationScopePiperPa34.is_deleted == False)
        .order_by(AuthorizationScopePiperPa34.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_authorization_scope_piper_pa34(
    session: AsyncSession,
    scope_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    obj = await session.get(AuthorizationScopePiperPa34, scope_id)
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
