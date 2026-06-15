import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base, ph_now


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"
    BULK_UPDATE = "BULK_UPDATE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    changed_fields = Column(JSON, nullable=True)
    performed_by_user_id = Column(
        Integer,
        ForeignKey("account_information.id"),
        nullable=True,
        index=True,
    )
    performed_by_name = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=ph_now,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=ph_now,
        onupdate=ph_now,
        server_default=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, module='{self.module_name}', "
            f"action='{self.action}', record_id={self.record_id})>"
        )
