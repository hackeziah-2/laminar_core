"""Account lookup helpers used by cross-module event publishers."""

from __future__ import annotations

from typing import List, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.models.role import Role


async def get_active_accounts_by_roles(
    session: AsyncSession,
    role_names: Sequence[str],
) -> List[AccountInformation]:
    """Return active accounts whose role name matches any given role."""
    names = [str(name).strip() for name in role_names if str(name).strip()]
    if not names:
        return []

    stmt = (
        select(AccountInformation)
        .join(Role, AccountInformation.role_id == Role.id)
        .where(AccountInformation.is_deleted.is_(False))
        .where(AccountInformation.status.is_(True))
        .where(Role.is_deleted.is_(False))
        .where(or_(*[Role.name.ilike(name) for name in names]))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
