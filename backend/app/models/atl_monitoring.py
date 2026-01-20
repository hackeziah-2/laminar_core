import enum
from xmlrpc.client import DateTime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Date,
    Time,
    Text,
    ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin


class LDNDMonitoring(Base,  TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ldnd_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False)
    inspection_type = Column(String(100), nullable=False)
    last_done_tach_due = Column(Float)
    last_done_tach_done = Column(Float)
    date_performed_start = Column(Date)
    date_performed_end = Column(Date)
    next_due = Column(Float)
    aircraft = relationship("Aircraft", back_populates="ldnd_records")
