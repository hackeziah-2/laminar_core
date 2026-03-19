import enum

from sqlalchemy import Boolean, Column, Integer, String, Date, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class CategoryTypeEnum(str, enum.Enum):
    COA = "COA"
    COR = "COR"
    NTC = "NTC"
    PITOT_STATIC = "PITOT_STATIC"
    TRANSPONDER = "TRANSPONDER"
    ELT = "ELT"
    WEIGHT_BALANCE = "WEIGHT_BALANCE"
    COMPASS_SWING = "COMPASS_SWING"
    MARKING_RESERVATION = "MARKING_RESERVATION"
    BINARY_CODE_24BIT = "BINARY_CODE_24BIT"
    IBRD_CORPAS = "IBRD_CORPAS"


class AircraftStatutoryCertificate(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "aircraft_statutory_certificates"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(
        Integer,
        ForeignKey("aircrafts.id"),
        nullable=False,
        index=True,
    )
    category_type = Column(
        PGEnum(CategoryTypeEnum, name="statutory_certificate_category_type", create_type=True),
        nullable=False,
    )
    date_of_expiration = Column(Date, nullable=True)
    web_link = Column(String(2048), nullable=True)
    file_path = Column(String(500), nullable=True)
    is_withhold = Column(Boolean, default=False, nullable=False)

    aircraft = relationship("Aircraft", back_populates="statutory_certificates")

    def __repr__(self):
        return f"<AircraftStatutoryCertificate(id={self.id}, aircraft_fk={self.aircraft_fk}, category={self.category_type})>"
