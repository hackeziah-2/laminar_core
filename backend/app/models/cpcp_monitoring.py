from datetime import date

from sqlalchemy import Column, Integer, String, Text, Float, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class CPCPMonitoring(Base, TimestampMixin, SoftDeleteMixin):
    """CPCP (Continuing Program Compliance Program) Monitoring."""

    __tablename__ = "cpcp_monitoring"

    id = Column(Integer, primary_key=True, index=True)

    inspection_operation = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    interval_hours = Column(Float, nullable=True)
    interval_months = Column(Float, nullable=True)

    last_done_tach = Column(Float, nullable=True)
    last_done_aftt = Column(Float, nullable=True)
    last_done_date = Column(Date, nullable=True)

    atl_ref = Column(Integer, ForeignKey("aircraft_technical_log.id"), nullable=True, index=True)

    atl = relationship("AircraftTechnicalLog", backref="cpcp_monitorings")

    def __repr__(self):
        return f"<CPCPMonitoring(id={self.id}, inspection_operation='{self.inspection_operation}')>"
