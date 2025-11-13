from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user_schema import UserCreate
from app.core.security import get_password_hash, verify_password
from typing import Optional

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalars().first()

async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    hashed = get_password_hash(user_in.password)
    obj = User(email=user_in.email, full_name=user_in.full_name, hashed_password=hashed)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
    
async def authenticate_user(session: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
