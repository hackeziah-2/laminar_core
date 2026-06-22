"""Notification log table for advisory reminder idempotency."""

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint

from app.database import Base, TimestampMixin, ph_now


class AdvisoryNotificationLog(Base, TimestampMixin):
    __tablename__ = "advisory_notification_logs"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_advisory_notification_logs_idempotency_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    advisory_source_id = Column(Integer, nullable=False, index=True)
    regulatory_compliance = Column(String(100), nullable=False, index=True)
    item = Column(String(255), nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    notification_type = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False, default=ph_now)
