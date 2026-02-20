from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin


class Module(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)

    role_permissions = relationship(
        "RolePermission",
        back_populates="module",
        cascade="all, delete-orphan"
    )
    user_permissions = relationship(
        "UserPermission",
        back_populates="module",
        cascade="all, delete-orphan"
    )
