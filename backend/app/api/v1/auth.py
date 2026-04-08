"""Authentication API using AccountInformation."""
from typing import List, Set, Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.api.deps import get_current_account
from app.schemas.auth_schema import Token, LoginResponse, AccountMe
from app.schemas.account_schema import AccountInformationCreate, AccountInformationRead
from app.repository.account_auth import authenticate_account
from app.repository.account import create_account_information, update_last_login
from app.core.security import create_access_token, _truncate_password
from app.models.account import AccountInformation

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """
    Login with username or email and password.
    OAuth2 compatible (username field accepts username or email).
    Returns JWT access token and account info.
    """
    password = (
        _truncate_password(form_data.password) if form_data.password else form_data.password
    )
    account = await authenticate_account(
        session,
        form_data.username.strip(),
        password,
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
        )
    await update_last_login(session, account.id)
    access_token = create_access_token(
        {"sub": str(account.id), "username": account.username}
    )
    full_name = f"{account.first_name} {account.last_name}".strip()
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        account_id=account.id,
        username=account.username,
        email=account.email,
        role_id=account.role_id,
        full_name=full_name,
    )


@router.post("/token", response_model=Token)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """
    OAuth2 token endpoint (for compatibility with OAuth2PasswordBearer).
    Same as /login but returns only access_token and token_type.
    """
    password = (
        _truncate_password(form_data.password) if form_data.password else form_data.password
    )
    account = await authenticate_account(
        session,
        form_data.username.strip(),
        password,
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
        )
    await update_last_login(session, account.id)
    access_token = create_access_token(
        {"sub": str(account.id), "username": account.username}
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/register",
    response_model=Union[List[AccountInformationRead], AccountInformationRead],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: Union[List[AccountInformationCreate], AccountInformationCreate],
    session: AsyncSession = Depends(get_session),
):
    """
    Create one or more AccountInformation records (register).
    Send a single object for one user, or a JSON array for bulk registration (atomic: all succeed or none).
    """
    if isinstance(payload, list):
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one account is required.",
            )
        seen_usernames: Set[str] = set()
        seen_emails: Set[str] = set()
        for item in payload:
            if item.username in seen_usernames:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate username in request: {item.username}",
                )
            seen_usernames.add(item.username)
            if item.email:
                if item.email in seen_emails:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Duplicate email in request: {item.email}",
                    )
                seen_emails.add(item.email)
        created: List[AccountInformationRead] = []
        for item in payload:
            created.append(
                await create_account_information(session, item, commit=False)
            )
        await session.commit()
        return created
    return await create_account_information(session, payload)


@router.get("/me", response_model=AccountMe)
@router.get("/me/", response_model=AccountMe)
async def me(
    account: AccountInformation = Depends(get_current_account),
):
    """Get current logged-in account profile. Requires valid JWT."""
    return AccountMe(
        full_name=account.full_name,
        role=account.role.name if account.role else None,
        designation=account.designation,
        email=account.email,
        username=account.username,
    )
