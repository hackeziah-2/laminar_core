from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class Role(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    account_informations = relationship(
        "AccountInformation",
        foreign_keys="[AccountInformation.role_id]",
        back_populates="role",
    )
    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan"
    )
