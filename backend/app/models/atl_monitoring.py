import enum

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Date,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class UnitEnum(str, enum.Enum):
    HRS = "HRS"
    CYCLES = "CYCLES"


class LDNDMonitoring(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ldnd_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    inspection_type = Column(String(100), nullable=False, index=True)
    unit = Column(
        PGEnum("HRS", "CYCLES", name="ldnd_unit", create_type=True),
        default="HRS",
        nullable=False,
    )
    last_done_tach_due = Column(Float, nullable=True)
    last_done_tach_done = Column(Float, nullable=True)
    next_due_tach_hours = Column(Float, nullable=True)
    performed_date_start = Column(Date, nullable=True)
    performed_date_end = Column(Date, nullable=True)

    aircraft = relationship("Aircraft", back_populates="ldnd_records")
