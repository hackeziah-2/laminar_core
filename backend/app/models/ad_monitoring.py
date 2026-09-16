from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class ADMonitoring(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """AD Monitoring (one) -> many WorkOrderADMonitoring. Belongs to one Aircraft via aircraft_fk."""

    __tablename__ = "ad_monitoring"
    __table_args__ = (
        Index(
            "ix_ad_monitoring_aircraft_fk_created_at_active",
            "aircraft_fk",
            "created_at",
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index(
            "ix_ad_monitoring_created_at_active",
            "created_at",
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index(
            "ix_ad_monitoring_compli_date_active",
            "compli_date",
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(
        Integer,
        ForeignKey("aircrafts.id"),
        nullable=False,
        index=True,
    )
    ad_number = Column(String(100), nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    inspection_interval = Column(String(100), nullable=False, index=True)
    compli_date = Column(Date, nullable=True)
    file_path = Column(String(500), nullable=True)
    web_link = Column(String(2048), nullable=True)

    aircraft = relationship("Aircraft", back_populates="ad_records")
    ad_works = relationship(
        "WorkOrderADMonitoring",
        back_populates="ad_monitoring",
        cascade="all, delete-orphan",
    )


class WorkOrderADMonitoring(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Work order for an AD; belongs to one ADMonitoring via ad_monitoring_fk."""

    __tablename__ = "workorder_ad_monitoring"
    __table_args__ = (
        Index(
            "ix_workorder_ad_monitoring_ad_fk_created_at_active",
            "ad_monitoring_fk",
            "created_at",
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index(
            "ix_workorder_ad_monitoring_last_done_date_active",
            "last_done_date",
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    ad_monitoring_fk = Column(
        Integer,
        ForeignKey("ad_monitoring.id"),
        nullable=False,
        index=True,
    )
    work_order_number = Column(String(50), nullable=False, index=True)
    last_done_aftt = Column(Float, nullable=True)
    last_done_tach = Column(Float, nullable=True)
    last_done_date = Column(Date, nullable=True)
    next_due_aftt = Column(Float, nullable=True)
    next_due_tach = Column(Float, nullable=True)
    atl_ref = Column(String(50), nullable=False, index=True)

    ad_monitoring = relationship(
        "ADMonitoring",
        back_populates="ad_works",
    )

