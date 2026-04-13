import os
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, declared_attr, relationship
from sqlalchemy import Boolean, Column, DateTime, Integer, ForeignKey, select
from sqlalchemy.sql import func


# Load database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/laminar_database"
)

# Async engine
engine = create_async_engine(DATABASE_URL, future=True)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# Dependency for async session
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# Mixin for timestamps
class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

# Mixin for soft deletes
class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)

    def soft_delete(self):
        self.is_deleted = True

    def hard_delete(self, session: AsyncSession):
        session.delete(self)

def active_query(model):
    return select(model).where(model.is_deleted.is_(False))

class AuditMixin:
    created_by = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("account_information.id"), nullable=True)

    @declared_attr
    def created_by_user(cls):
        return relationship(
            "AccountInformation",
            foreign_keys=[cls.created_by],
        )

    @declared_attr
    def updated_by_user(cls):
        return relationship(
            "AccountInformation",
            foreign_keys=[cls.updated_by],
        )


async def set_audit_fields(obj: Any, user_id: int, is_create: bool = False) -> None:
    """Set created_by / updated_by from the acting account (account_information.id)."""
    if is_create:
        obj.created_by = user_id
    obj.updated_by = user_id
