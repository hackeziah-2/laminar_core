from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.account_auth import get_account_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_account(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> AccountInformation:
    """Get current account from JWT. Raises 401 if invalid."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    account_id = payload.get("sub")
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    account = await get_account_by_id(session, int(account_id))
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found",
        )
    return account


async def get_current_active_account(
    account: AccountInformation = Depends(get_current_account),
) -> AccountInformation:
    """Require active account (status=True)."""
    if not account.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return account


def require_permission(module_name: str, action: str):
    """
    Dependency factory: require account to have permission on module.
    action: 'can_read', 'can_write', 'can_approve'
    Use: Depends(require_permission("account-information", "can_write"))
    """
    from sqlalchemy import select

    async def _check(
        account: AccountInformation = Depends(get_current_active_account),
        session: AsyncSession = Depends(get_session),
    ) -> AccountInformation:
        # Load role and user_permissions
        from app.models.module import Module
        from app.models.role_permission import RolePermission
        from app.models.user_permission import UserPermission

        result = await session.execute(
            select(Module).where(Module.name == module_name, Module.is_deleted == False)
        )
        module = result.scalar_one_or_none()
        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_name}' not found",
            )

        # Check user override permission
        up_result = await session.execute(
            select(UserPermission).where(
                UserPermission.account_id == account.id,
                UserPermission.module_id == module.id,
                UserPermission.is_deleted == False,
            )
        )
        user_perm = up_result.scalar_one_or_none()
        if user_perm and getattr(user_perm, action, False):
            return account

        # Check role permission
        if account.role_id:
            rp_result = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == account.role_id,
                    RolePermission.module_id == module.id,
                    RolePermission.is_deleted == False,
                )
            )
            role_perm = rp_result.scalar_one_or_none()
            if role_perm and getattr(role_perm, action, False):
                return account

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {action} on {module_name}",
        )

    return _check
