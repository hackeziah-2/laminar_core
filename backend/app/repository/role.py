from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.account import AccountInformation
from app.models.module import Module
from app.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
)
from app.repository.module import get_module_by_name


async def create_role(
    session: AsyncSession,
    data: RoleCreate,
    *,
    audit_account_id: Optional[int] = None,
) -> Role:
    """Create a new Role and optional permissions. Returns Role ORM with permissions loaded."""
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

    role_data = {k: v for k, v in data.dict().items() if k != "permissions"}
    role = Role(**role_data)
    session.add(role)
    await session.flush()

    permissions = getattr(data, "permissions", None) or []
    for perm in permissions:
        module = await get_module_by_name(session, perm.module)
        if not module:
            raise HTTPException(
                status_code=400,
                detail=f"Module not found: {perm.module!r}",
            )
        rp = RolePermission(
            role_id=role.id,
            module_id=module.id,
            can_read=perm.read,
            can_write=perm.create or perm.update or perm.delete,
            can_create=perm.create,
            can_update=perm.update,
            can_delete=perm.delete,
            can_approve=perm.approve,
        )
        session.add(rp)
        if audit_account_id is not None:
            await set_audit_fields(rp, audit_account_id, is_create=True)

    if audit_account_id is not None:
        await set_audit_fields(role, audit_account_id, is_create=True)

    await session.commit()
    await session.refresh(role)
    return role


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


async def get_role_with_permissions(
    session: AsyncSession,
    role_id: int
) -> Optional[Role]:
    """Get a Role by ID with permissions and module names loaded."""
    result = await session.execute(
        select(Role)
        .where(Role.id == role_id)
        .where(Role.is_deleted == False)
        .options(selectinload(Role.permissions).selectinload(RolePermission.module))
    )
    return result.scalar_one_or_none()


async def update_role(
    session: AsyncSession,
    role_id: int,
    role_in: RoleUpdate,
    *,
    audit_account_id: Optional[int] = None,
) -> Optional[RoleRead]:
    """Update a Role and optionally replace its permissions."""
    obj = await session.get(Role, role_id)
    if not obj or obj.is_deleted:
        return None

    update_data = role_in.dict(exclude_unset=True)
    permissions_payload = update_data.pop("permissions", None)

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

    if permissions_payload is not None:
        # Load all existing permissions for this role (including soft-deleted)
        # so we can reuse rows and avoid violating uq_role_module.
        existing_result = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        existing_by_module = {
            rp.module_id: rp for rp in existing_result.scalars().all()
        }
        payload_module_ids = set()
        for perm in permissions_payload:
            module = await get_module_by_name(session, perm["module"])
            if not module:
                raise HTTPException(
                    status_code=400,
                    detail=f"Module not found: {perm['module']!r}",
                )
            payload_module_ids.add(module.id)
            rp = existing_by_module.get(module.id)
            if rp:
                rp.is_deleted = False
                rp.can_read = perm.get("read", False)
                c = perm.get("create", False)
                u = perm.get("update", False)
                d = perm.get("delete", False)
                rp.can_create = c
                rp.can_update = u
                rp.can_delete = d
                rp.can_write = c or u or d
                rp.can_approve = perm.get("approve", False)
                session.add(rp)
            else:
                c = perm.get("create", False)
                u = perm.get("update", False)
                d = perm.get("delete", False)
                session.add(
                    RolePermission(
                        role_id=role_id,
                        module_id=module.id,
                        can_read=perm.get("read", False),
                        can_write=c or u or d,
                        can_create=c,
                        can_update=u,
                        can_delete=d,
                        can_approve=perm.get("approve", False),
                    )
                )
        # Soft-delete permissions for modules no longer in the payload
        for module_id, rp in existing_by_module.items():
            if module_id not in payload_module_ids and not rp.is_deleted:
                rp.soft_delete()
                session.add(rp)

    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
        rp_all = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        for rp in rp_all.scalars().all():
            await set_audit_fields(rp, audit_account_id, is_create=False)
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
) -> List[Tuple[Role, int]]:
    """Get all Roles with user count (no pagination, for dropdowns)."""
    user_count_subq = (
        select(func.count())
        .select_from(AccountInformation)
        .where(
            AccountInformation.role_id == Role.id,
            AccountInformation.is_deleted == False,
        )
        .scalar_subquery()
    )
    stmt = (
        select(Role, user_count_subq.label("user_count"))
        .where(Role.is_deleted == False)
        .order_by(Role.name.asc())
    )
    result = await session.execute(stmt)
    return [(row[0], row[1] or 0) for row in result.all()]


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
