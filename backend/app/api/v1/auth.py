"""Authentication API using AccountInformation."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


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


@router.post("/register", response_model=AccountInformationRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: AccountInformationCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new AccountInformation (register)."""
    return await create_account_information(session, payload)


@router.get("/me", response_model=AccountMe)
async def me(
    account: AccountInformation = Depends(get_current_account),
):
    """Get current logged-in account info. Requires valid JWT."""
    return account
