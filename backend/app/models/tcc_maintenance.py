import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.database import Base, TimestampMixin, SoftDeleteMixin


# String values for PostgreSQL ENUM (asyncpg works reliably with string-based ENUM)
METHOD_OF_COMPLIANCE_VALUES = (
    "Overhaul",
    "Replacement",
    "Inspection",
    "I&S",
    "Operational Test",
    "Calibration",
)

# Single shared ENUM type for both columns (string-based for asyncpg compatibility)
method_of_compliance_enum = PGEnum(
    *METHOD_OF_COMPLIANCE_VALUES,
    name="method_of_compliance_enum",
    create_type=True,
)


# Category values for PostgreSQL ENUM (Powerplant, Airframe, Inspection Servicing)
TCC_CATEGORY_VALUES = (
    "Powerplant",
    "Airframe",
    "Inspection Servicing",
)

tcc_category_enum = PGEnum(
    *TCC_CATEGORY_VALUES,
    name="tcc_category_enum",
    create_type=True,
)


class TCCCategoryEnum(str, enum.Enum):
    """Python enum for Category; use .value when persisting to DB."""
    POWERPLANT = "Powerplant"
    AIRFRAME = "Airframe"
    INSPECTION_SERVICING = "Inspection Servicing"


class MethodOfComplianceEnum(str, enum.Enum):
    """Python enum for validation; use .value when persisting to DB."""
    OVERHAUL = "Overhaul"
    REPLACEMENT = "Replacement"
    INSPECTION = "Inspection"
    IS = "I&S"
    OPERATIONAL_TEST = "Operational Test"
    CALIBRATION = "Calibration"


class TCCMaintenance(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tcc_maintenance"

    id = Column(Integer, primary_key=True, index=True)

    category = Column(
        tcc_category_enum,
        nullable=True,
    )

    part_number = Column(String, nullable=False)
    serial_number = Column(String, nullable=True)
    description = Column(String, nullable=True)

    component_limit_years = Column(Float, nullable=True)
    component_limit_hours = Column(Float, nullable=True)

    component_method_of_compliance = Column(
        method_of_compliance_enum,
        nullable=True,
    )

    last_done_date = Column(Date, nullable=True)
    last_done_tach = Column(Float, nullable=True)
    last_done_aftt = Column(Float, nullable=True)

    last_done_method_of_compliance = Column(
        method_of_compliance_enum,
        nullable=True,
    )

    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    atl_ref = Column(Integer, ForeignKey("aircraft_technical_log.id"), nullable=True, index=True)

    aircraft = relationship("Aircraft", back_populates="tcc_maintenances")
    atl = relationship("AircraftTechnicalLog", back_populates="tcc_maintenances")

    def __repr__(self):
        return f"<TCCMaintenance(id={self.id}, part_number='{self.part_number}', aircraft_fk={self.aircraft_fk})>"
