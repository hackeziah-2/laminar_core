import enum

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
from app.models.aircraft import Aircraft
from app.database import Base, TimestampMixin, SoftDeleteMixin


class AircraftLogbookEntry(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "aircraft_logbook_entries"

    id = Column(Integer, primary_key=True, index=True)

    aircraft_id = Column(
        Integer,
        ForeignKey("aircrafts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    aircraft = relationship(Aircraft, lazy="joined", back_populates="logbook_entries")

    sequence_no = Column(String(50), unique=True, nullable=False)
    nature_of_flight = Column(String(50), nullable=True)
    nature_others = Column(String(100), nullable=True)

    # Off / On blocks
    off_blocks_station = Column(String(10), nullable=False)
    off_blocks_date = Column(Date, nullable=False)
    off_blocks_time = Column(Time, nullable=False)

    on_blocks_station = Column(String(10), nullable=False)
    on_blocks_date = Column(Date, nullable=False)
    on_blocks_time = Column(Time, nullable=False)

    total_flight_time = Column(Float, nullable=False)

    # Tach / Hobbs
    tach_start = Column(Float, nullable=False)
    tach_end = Column(Float, nullable=False)
    tach_total = Column(Float, nullable=False)

    hobbs_start = Column(Float, nullable=False)
    hobbs_end = Column(Float, nullable=False)
    hobbs_total = Column(Float, nullable=False)

    # Notes
    pilot_report = Column(Text)
    maintenance_entry = Column(Text)
    actions_taken = Column(Text)

    # Component times
    airframe_time = Column(Float, nullable=False)
    engine_time = Column(Float, nullable=False)
    propeller_time = Column(Float, nullable=False)

    def __repr__(self):
        return f"<ATL(seq='{self.sequence_no}')>"
