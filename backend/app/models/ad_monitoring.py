from sqlalchemy import Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class ADMonitoring(Base, TimestampMixin, SoftDeleteMixin):
    """AD Monitoring (one) -> many WorkOrderADMonitoring. Belongs to one Aircraft via aircraft_fk."""

    __tablename__ = "ad_monitoring"

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

    aircraft = relationship("Aircraft", back_populates="ad_records")
    ad_works = relationship(
        "WorkOrderADMonitoring",
        back_populates="ad_monitoring",
        cascade="all, delete-orphan",
    )


class WorkOrderADMonitoring(Base, TimestampMixin, SoftDeleteMixin):
    """Work order for an AD; belongs to one ADMonitoring via ad_monitoring_fk."""

    __tablename__ = "workorder_ad_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    ad_monitoring_fk = Column(
        Integer,
        ForeignKey("ad_monitoring.id"),
        nullable=False,
        index=True,
    )
    work_order_number = Column(String(50), nullable=False, index=True)
    last_done_actt = Column(Float, nullable=True)
    last_done_tach = Column(Float, nullable=True)
    last_done_date = Column(Date, nullable=True)
    next_done_actt = Column(Float, nullable=True)
    tach = Column(Float, nullable=True)
    atl_ref = Column(String(50), nullable=False, index=True)

    ad_monitoring = relationship(
        "ADMonitoring",
        back_populates="ad_works",
    )

