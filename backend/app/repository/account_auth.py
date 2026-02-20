"""Authentication and lookup for AccountInformation."""
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.core.security import verify_password


async def get_account_by_id(
    session: AsyncSession,
    account_id: int,
) -> Optional[AccountInformation]:
    """Get AccountInformation by ID (excludes soft-deleted)."""
    result = await session.execute(
        select(AccountInformation)
        .where(AccountInformation.id == account_id)
        .where(AccountInformation.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def authenticate_account(
    session: AsyncSession,
    username_or_email: str,
    password: str,
) -> Optional[AccountInformation]:
    """
    Authenticate by username or email and password.
    Returns AccountInformation if credentials are valid.
    """
    result = await session.execute(
        select(AccountInformation)
        .where(
            or_(
                AccountInformation.username == username_or_email,
                AccountInformation.email == username_or_email,
            )
        )
        .where(AccountInformation.is_deleted == False)
    )
    account = result.scalar_one_or_none()
    if not account:
        return None
    if not account.status:
        return None  # inactive account
    if not verify_password(password, account.password):
        return None
    return account
