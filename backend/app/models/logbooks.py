from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Date,
    Text,
    ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin

class EngineLogbook(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "engine_logbook"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    engine_tsn = Column(Float, nullable=True)  # Engine Time Since New
    sequence_no = Column(String(50), nullable=False, index=True)
    tach_time = Column(Float, nullable=True)
    engine_tso = Column(Float, nullable=True)  # Engine Time Since Overhaul
    engine_tbo = Column(Float, nullable=True)  # Engine Time Between Overhaul
    description = Column(Text, nullable=True)
    mechanic_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    signature = Column(String(255), nullable=True)
    upload_file = Column(String(500), nullable=True)  # File path for uploaded file

    aircraft = relationship("Aircraft", foreign_keys=[aircraft_fk], back_populates="engine_logbooks")
    mechanic = relationship("AccountInformation", foreign_keys=[mechanic_fk])

    def __repr__(self):
        return f"<EngineLogbook(id={self.id}, seq='{self.sequence_no}')>"

class AirframeLogbook(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "airframe_logbook"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    sequence_no = Column(String(50), nullable=False, index=True)
    tach_time = Column(Float, nullable=True)
    airframe_time = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    mechanic_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    signature = Column(String(255), nullable=True)
    upload_file = Column(String(500), nullable=True)  # File path for uploaded file

    aircraft = relationship("Aircraft", foreign_keys=[aircraft_fk], back_populates="airframe_logbooks")
    mechanic = relationship("AccountInformation", foreign_keys=[mechanic_fk])

    def __repr__(self):
        return f"<AirframeLogbook(id={self.id}, seq='{self.sequence_no}')>"


class AvionicsLogbook(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "avionics_logbook"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    airframe_tsn = Column(Float, nullable=True)  # Airframe Time Since New
    sequence_no = Column(String(50), nullable=False, index=True)
    component = Column(String(255), nullable=True)
    part_no = Column(String(100), nullable=True)
    serial_no = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    mechanic_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    signature = Column(String(255), nullable=True)
    upload_file = Column(String(500), nullable=True)  # File path for uploaded file

    aircraft = relationship("Aircraft", foreign_keys=[aircraft_fk], back_populates="avionics_logbooks")
    mechanic = relationship("AccountInformation", foreign_keys=[mechanic_fk])

    def __repr__(self):
        return f"<AvionicsLogbook(id={self.id}, seq='{self.sequence_no}')>"

class PropellerLogbook(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "propeller_logbook"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    propeller_tsn = Column(Float, nullable=True)  # Propeller Time Since New
    sequence_no = Column(String(50), nullable=False, index=True)
    tach_time = Column(Float, nullable=True)
    propeller_tso = Column(Float, nullable=True)  # Propeller Time Since Overhaul
    propeller_tbo = Column(Float, nullable=True)  # Propeller Time Between Overhaul
    description = Column(Text, nullable=True)
    mechanic_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    signature = Column(String(255), nullable=True)
    upload_file = Column(String(500), nullable=True)  # File path for uploaded file

    aircraft = relationship("Aircraft", foreign_keys=[aircraft_fk], back_populates="propeller_logbooks")
    mechanic = relationship("AccountInformation", foreign_keys=[mechanic_fk])

    def __repr__(self):
        return f"<PropellerLogbook(id={self.id}, seq='{self.sequence_no}')>"
