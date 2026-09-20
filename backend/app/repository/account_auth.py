"""Authentication and lookup for AccountInformation."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import AccountInformation
from app.core.security import verify_password


async def get_account_by_id(
    session: AsyncSession,
    account_id: int,
) -> Optional[AccountInformation]:
    """Get AccountInformation by ID (excludes soft-deleted)."""
    result = await session.execute(
        select(AccountInformation)
        .options(selectinload(AccountInformation.role))
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
    Username is unique; email may be shared, so email login matches the
    first active account whose password is valid.
    """
    username_result = await session.execute(
        select(AccountInformation)
        .where(AccountInformation.username == username_or_email)
        .where(AccountInformation.is_deleted == False)
    )
    account = username_result.scalar_one_or_none()
    if account:
        if not account.status:
            return None
        if not verify_password(password, account.password):
            return None
        return account

    email_result = await session.execute(
        select(AccountInformation)
        .where(AccountInformation.email == username_or_email)
        .where(AccountInformation.is_deleted == False)
        .where(AccountInformation.status == True)
    )
    for candidate in email_result.scalars().all():
        if verify_password(password, candidate.password):
            return candidate
    return None
