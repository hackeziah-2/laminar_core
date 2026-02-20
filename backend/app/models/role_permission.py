from sqlalchemy import Column, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin


class RolePermission(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False, index=True)

    can_read = Column(Boolean, default=False)
    can_write = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)

    role = relationship("Role", back_populates="permissions")
    module = relationship("Module", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "module_id", name="uq_role_module"),
    )
