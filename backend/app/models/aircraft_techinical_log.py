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
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from app.database import Base, TimestampMixin, SoftDeleteMixin


class TypeEnum(str, enum.Enum):
    TR = "TR"
    PSF = "PSF"
    PRF = "PRF"
    EGR = "EGR"
    ME = "ME"
    TR_WITH_PIREM = "TR_WITH_PIREM"
    VOID = "VOID"


class AircraftTechnicalLog(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "aircraft_technical_log"

    id = Column(Integer, primary_key=True, index=True)

    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False)
    sequence_no = Column(String(50), nullable=False)

    nature_of_flight = Column(
        PGEnum(TypeEnum, name="nature_of_flight", create_type=True),
        nullable=True,
    )
    next_inspection_due = Column(String(100), nullable=True)
    tach_time_due = Column(Float, nullable=True)

    origin_station = Column(String(50), nullable=True)
    origin_date = Column(Date, nullable=True)
    origin_time = Column(Time(timezone=False), nullable=True)

    destination_station = Column(String(50), nullable=True)
    destination_date = Column(Date, nullable=True)
    destination_time = Column(Time(timezone=False), nullable=True)

    number_of_landings = Column(Integer, nullable=True)

    hobbs_meter_start = Column(Float, nullable=True)
    hobbs_meter_end = Column(Float, nullable=True)
    hobbs_meter_total = Column(Float, nullable=True)

    tachometer_start = Column(Float, nullable=True)
    tachometer_end = Column(Float, nullable=True)
    tachometer_total = Column(Float, nullable=True)

    # Airframe time fields
    airframe_prev_time = Column(Float, nullable=True)
    airframe_flight_time = Column(Float, nullable=True)
    airframe_total_time = Column(Float, nullable=True)
    airframe_run_time = Column(Float, nullable=True)
    airframe_aftt = Column(Float, nullable=True)

    # Engine time fields
    engine_prev_time = Column(Float, nullable=True)
    engine_flight_time = Column(Float, nullable=True)
    engine_total_time = Column(Float, nullable=True)
    engine_run_time = Column(Float, nullable=True)
    engine_tsn = Column(String(100), nullable=True)
    engine_tso = Column(Float, nullable=True)
    engine_tbo = Column(Float, nullable=True)

    # Propeller time fields
    propeller_prev_time = Column(Float, nullable=True)
    propeller_flight_time = Column(Float, nullable=True)
    propeller_total_time = Column(Float, nullable=True)
    propeller_run_time = Column(Float, nullable=True)
    propeller_tsn = Column(Float, nullable=True)
    propeller_tso = Column(Float, nullable=True)
    propeller_tbo = Column(Float, nullable=True)

    # Life time limits
    life_time_limit_engine = Column(Float, nullable=True)
    life_time_limit_propeller = Column(Float, nullable=True)

    fuel_qty_left_uplift_qty = Column(Float)
    fuel_qty_right_uplift_qty = Column(Float)

    fuel_qty_left_prior_departure = Column(Float)
    fuel_qty_right_prior_departure = Column(Float)

    fuel_qty_left_after_on_blks = Column(Float)
    fuel_qty_right_after_on_blks = Column(Float)

    oil_qty_uplift_qty = Column(Float)
    oil_qty_prior_departure = Column(Float)
    oil_qty_after_on_blks = Column(Float)

    remarks = Column(Text)
    actions_taken = Column(Text)

    remark_person = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    actiontaken_person = Column(Integer, ForeignKey("account_information.id"), nullable=True)

    pilot_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    maintenance_fk = Column(Integer, ForeignKey("account_information.id"), nullable=True)

    pilot_accepted_by = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    pilot_accept_date = Column(Date, nullable=True)
    pilot_accept_time = Column(Time(timezone=False), nullable=True)

    rts_signed_by = Column(Integer, ForeignKey("account_information.id"), nullable=True)
    rts_date = Column(Date, nullable=True)
    rts_time = Column(Time(timezone=False), nullable=True)

    white_atl = Column(Text)
    dfp =  Column(Text)

    aircraft = relationship("Aircraft", back_populates="atl_logs")
    component_parts = relationship(
        "ComponentPartsRecord",
        back_populates="atl",
        cascade="all, delete-orphan"
    )
    tcc_maintenances = relationship("TCCMaintenance", foreign_keys="TCCMaintenance.atl_ref", back_populates="atl")

    def __repr__(self):
        return f"<ATL(seq='{self.sequence_no}')>"


class ComponentPartsRecord(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "component_parts_record"

    id = Column(Integer, primary_key=True, index=True)

    atl_fk = Column(Integer, ForeignKey("aircraft_technical_log.id"), nullable=False)

    qty = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)

    nomenclature = Column(String(255), nullable=False)

    removed_part_no = Column(String(100))
    removed_serial_no = Column(String(100))

    installed_part_no = Column(String(100))
    installed_serial_no = Column(String(100))

    part_description = Column(Text)
    ata_chapter = Column(String(50))

    atl = relationship("AircraftTechnicalLog", back_populates="component_parts")
    
    def __repr__(self):
        return f"<ComponentPartsRecord(id={self.id}, desc='{self.part_description}')>"
