import enum

from sqlalchemy import Column, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class StatusEnum(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    MAINTENANCE = "Maintenance"

class Aircraft(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "aircrafts"
    
    id = Column(Integer, primary_key=True, index=True)
    registration = Column(String(89), nullable=False, unique=True, index=True)
    manufacturer = Column(String(89), nullable=False, index=True)
    report_description = Column(Text, nullable=True)
    type = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    msn = Column(String, nullable=False, unique=True, index=True)
    base = Column(String, nullable=False, index=True)
    ownership = Column(String, nullable=False)
    status = Column(
        PGEnum(StatusEnum, name="status", create_type=True),  # PostgreSQL enum
        default=StatusEnum.ACTIVE,
        nullable=False
    )

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

    logbook_entries = relationship("AircraftLogbookEntry", back_populates="aircraft")

    atl_logs = relationship("AircraftTechnicalLog", back_populates="aircraft")
    ldnd_records = relationship("LDNDMonitoring", back_populates="aircraft")

    engine_logbooks = relationship("EngineLogbook", foreign_keys="EngineLogbook.aircraft_fk", back_populates="aircraft")
    airframe_logbooks = relationship("AirframeLogbook", foreign_keys="AirframeLogbook.aircraft_fk", back_populates="aircraft")
    avionics_logbooks = relationship("AvionicsLogbook", foreign_keys="AvionicsLogbook.aircraft_fk", back_populates="aircraft")
    propeller_logbooks = relationship("PropellerLogbook", foreign_keys="PropellerLogbook.aircraft_fk", back_populates="aircraft")

    def __repr__(self):
        return f"<Aircraft(reg='{self.registration}', type='{self.type}', model='{self.model}')>"


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


class AirframeTable(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "airframe_tables"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(144), nullable=False, index=True)
    msd = Column(String(144), nullable=False, index=True)
    arc = Column(String(144), nullable=False, index=True)
    report_description = Column(Text)
