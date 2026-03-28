from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.database import Base, TimestampMixin, AuditMixin
from app.models.aircraft_statutory_certificate import CategoryTypeEnum


class AircraftStatutoryCertificateHistory(Base, TimestampMixin, AuditMixin):
    __tablename__ = "aircraft_statutory_certificates_history"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(
        Integer,
        ForeignKey("aircrafts.id"),
        nullable=False,
        index=True,
    )
    asc_history = Column(
        Integer,
        ForeignKey("aircraft_statutory_certificates.id"),
        nullable=True,
        index=True,
    )
    category_type = Column(
        PGEnum(CategoryTypeEnum, name="statutory_certificate_category_type", create_type=False),
        nullable=False,
    )
    date_of_expiration = Column(Date, nullable=True)
    web_link = Column(String(2048), nullable=True)

    def __repr__(self):
        return (
            f"<AircraftStatutoryCertificateHistory(id={self.id}, "
            f"aircraft_fk={self.aircraft_fk}, category={self.category_type})>"
        )
