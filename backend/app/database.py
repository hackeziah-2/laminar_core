import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, declared_attr, relationship
from sqlalchemy import Boolean, Column, DateTime, Integer, ForeignKey, select
from sqlalchemy.sql import func

# Philippine timezone – use ph_now() for all app-generated timestamps
PH_TZ = ZoneInfo("Asia/Manila")


def ph_now() -> datetime:
    return datetime.now(PH_TZ)


# Load database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/laminar_database"
)

# Async engine – PostgreSQL session timezone pinned to Asia/Manila so that
# now()/CURRENT_TIMESTAMP and timestamptz rendering use PH time regardless of host TZ
engine = create_async_engine(
    DATABASE_URL,
    future=True,
    connect_args={"server_settings": {"timezone": "Asia/Manila"}},
)

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

# Mixin for timestamps – generated in Asia/Manila (PH) time
class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        default=ph_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=ph_now,
        onupdate=ph_now,
        server_default=func.now(),
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


async def soft_delete(record: Any, db: AsyncSession) -> Any:
    """Soft-delete a record that has a deleted_at column (stamped with PH time)."""
    record.deleted_at = ph_now()
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
