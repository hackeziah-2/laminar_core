import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from app.database import Base, TimestampMixin, SoftDeleteMixin


class AircraftStatus(str, enum.Enum):
    ACTIVE = "Active"
    MAINTENANCE = "Maintenance"
    GROUNDED = "Grounded"

class Aircraft(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "aircrafts"
    id = Column(Integer, primary_key=True, index=True)
    aircraft_registry = Column(String(89), nullable=False, index=True)
    manufacturer = Column(String(89), nullable=False, index=True)
    report_description = Column(Text)
    
    type = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    msn = Column(String, nullable=False, unique=True, index=True)
    reg_no = Column(String, nullable=False, unique=True, index=True)
    base = Column(String, nullable=False, index=True)
    ownership = Column(String, nullable=False)
    status = Column(SQLEnum(AircraftStatus), default=AircraftStatus.ACTIVE, nullable=False)

    # Airframe Information
    airframe_model = Column(String, nullable=True)
    airframe_service_manual = Column(String, nullable=True)
    airframe_serial_number = Column(String, nullable=True)
    airframe_ipc = Column(String, nullable=True)
    
    # Engine Information
    engine_model = Column(String, nullable=True)
    engine_serial_number = Column(String, nullable=True)
    engine_arc = Column(String, nullable=True)
    
    # Propeller Information
    propeller_model = Column(String, nullable=True)
    propeller_serial_number = Column(String, nullable=True)
    propeller_arc = Column(String, nullable=True)

    def __repr__(self):
        return f"<Aircraft(reg_no='{self.reg_no}', type='{self.type}', model='{self.model}')>"


class Airframe(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "airframe"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(144), nullable=False, index=True)
    msd = Column(String(144), nullable=False, index=True)
    arc = Column(String(144), nullable=False, index=True)
    report_description = Column(Text)

class Engine(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "engine"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(144), nullable=False, index=True)
    msd = Column(String(144), nullable=False, index=True)
    arc = Column(String(144), nullable=False, index=True)
    report_description = Column(Text)


class Propeller(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "propeller"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(144), nullable=False, index=True)
    msd = Column(String(144), nullable=False, index=True)
    arc = Column(String(144), nullable=False, index=True)
    report_description = Column(Text)
