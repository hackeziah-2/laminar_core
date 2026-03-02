import enum

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.database import Base, TimestampMixin, SoftDeleteMixin


FLEET_DAILY_UPDATE_STATUS_VALUES = (
    "Running",
    "Ongoing Maintenance",
    "AOG",
)

fleet_daily_update_status_enum = PGEnum(
    *FLEET_DAILY_UPDATE_STATUS_VALUES,
    name="fleet_daily_update_status_enum",
    create_type=True,
)


class FleetDailyUpdateStatusEnum(str, enum.Enum):
    RUNNING = "Running"
    ONGOING_MAINTENANCE = "Ongoing Maintenance"
    AOG = "AOG"


class FleetDailyUpdate(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "fleet_daily_update"

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    aircraft_fk = Column(
        Integer,
        ForeignKey("aircrafts.id"),
        nullable=False,
        index=True,
        unique=True,
    )
    aircraft = relationship("Aircraft", back_populates="fleet_daily_update", uselist=False)

    status = Column(
        fleet_daily_update_status_enum,
        nullable=False,
        default=FleetDailyUpdateStatusEnum.RUNNING.value,
    )

    next_insp_due = Column(Float, nullable=True)
    tach_time_due = Column(Float, nullable=True)
    tach_time_eod = Column(Float, nullable=True)
    remaining_time_before_next_isp = Column(Float, nullable=True)
    remaining_time_before_engine = Column(Float, nullable=True)
    remaining_time_before_propeller = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)

    def __repr__(self):
        return f"<FleetDailyUpdate(id={self.id}, aircraft_fk={self.aircraft_fk}, status='{self.status}')>"
