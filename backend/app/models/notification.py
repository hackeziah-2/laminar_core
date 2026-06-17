"""Notification ORM model."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.database import Base, PublicUuidMixin, TimestampMixin, ph_now
from app.enums.notification import (
    NotificationSeverity,
    NotificationStatus,
    NotificationType,
)

NOTIFICATION_MODULE_NAME = "Notifications"


class Notification(Base, TimestampMixin, PublicUuidMixin):
    """In-app notification for a single recipient account."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_status_created", "recipient_account_id", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recipient_account_id = Column(
        Integer,
        ForeignKey("account_information.id"),
        nullable=False,
        index=True,
    )
    sender_account_id = Column(
        Integer,
        ForeignKey("account_information.id"),
        nullable=True,
        index=True,
    )
    sender_initials = Column(String(5), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    module_name = Column(String(100), nullable=False, index=True)
    type = Column(
        PGEnum(
            NotificationType,
            name="notification_type_enum",
            create_type=True,
        ),
        nullable=False,
        index=True,
    )
    severity = Column(
        PGEnum(
            NotificationSeverity,
            name="notification_severity_enum",
            create_type=True,
        ),
        nullable=False,
        index=True,
    )
    status = Column(
        PGEnum(
            NotificationStatus,
            name="notification_status_enum",
            create_type=True,
        ),
        nullable=False,
        default=NotificationStatus.UNREAD,
        server_default=NotificationStatus.UNREAD.value,
        index=True,
    )
    reference_id = Column(Integer, nullable=True, index=True)
    reference_type = Column(String(100), nullable=True, index=True)
    notification_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    recipient = relationship(
        "AccountInformation",
        foreign_keys=[recipient_account_id],
        back_populates="notifications_received",
    )
    sender = relationship(
        "AccountInformation",
        foreign_keys=[sender_account_id],
        back_populates="notifications_sent",
    )

    def mark_read(self) -> None:
        """Transition to READ and stamp read_at."""
        self.status = NotificationStatus.READ
        self.read_at = ph_now()

    def mark_archived(self) -> None:
        """Soft-archive the notification."""
        self.status = NotificationStatus.ARCHIVED
        self.archived_at = ph_now()

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, recipient_account_id={self.recipient_account_id}, "
            f"status='{self.status}', title='{self.title}')>"
        )
