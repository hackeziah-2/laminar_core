from sqlalchemy import Column, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin


class UserPermission(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("account_information.id"),
        nullable=False,
        index=True
    )
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False, index=True)

    can_read = Column(Boolean, default=False)
    can_write = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)

    account_information = relationship(
        "AccountInformation",
        back_populates="user_permissions"
    )
    module = relationship("Module", back_populates="user_permissions")

    __table_args__ = (
        UniqueConstraint("account_id", "module_id", name="uq_account_module"),
    )
