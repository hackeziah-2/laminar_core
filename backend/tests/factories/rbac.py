"""Seed RBAC rows for API tests."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.account import AccountInformation
from app.models.module import Module
from app.models.role import Role
from app.models.role_permission import RolePermission


async def seed_module(
    session: AsyncSession,
    name: str,
) -> int:
    mod = Module(name=name)
    session.add(mod)
    await session.flush()
    return mod.id


async def seed_role(session: AsyncSession, name: Optional[str] = None) -> int:
    role = Role(
        name=name or f"Test Role {uuid.uuid4().hex[:8]}",
        description="pytest role",
    )
    session.add(role)
    await session.flush()
    return role.id


async def seed_role_permission(
    session: AsyncSession,
    *,
    role_id: int,
    module_id: int,
    can_read: bool = False,
    can_create: bool = False,
    can_update: bool = False,
    can_delete: bool = False,
) -> None:
    session.add(
        RolePermission(
            role_id=role_id,
            module_id=module_id,
            can_read=can_read,
            can_create=can_create,
            can_update=can_update,
            can_delete=can_delete,
        )
    )


async def seed_account(
    session: AsyncSession,
    *,
    role_id: int,
    username: Optional[str] = None,
) -> int:
    uname = username or f"pytest_{uuid.uuid4().hex[:12]}"
    account = AccountInformation(
        first_name="Test",
        last_name="User",
        username=uname,
        password=get_password_hash("pytestpass123"),
        status=True,
        role_id=role_id,
    )
    session.add(account)
    await session.flush()
    return account.id


async def seed_account_with_module_permissions(
    session: AsyncSession,
    module_permissions: dict[str, dict[str, bool]],
) -> tuple[int, int]:
    """
    Seed one role, one account, and permissions per module name.

    module_permissions example::
        {"General Information": {"can_create": True, "can_read": True}}
    """
    role_id = await seed_role(session)
    for module_name, perms in module_permissions.items():
        module_id = await seed_module(session, module_name)
        await seed_role_permission(
            session,
            role_id=role_id,
            module_id=module_id,
            can_read=perms.get("can_read", False),
            can_create=perms.get("can_create", False),
            can_update=perms.get("can_update", False),
            can_delete=perms.get("can_delete", False),
        )
    account_id = await seed_account(session, role_id=role_id)
    await session.commit()
    return account_id, role_id
