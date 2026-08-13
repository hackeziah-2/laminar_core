from sqlalchemy import Column, Integer, Text, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin
from app.models.aircraft_techinical_log import TypeEnum


class NatureOfFlightDescription(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "nature_of_flight_description"
    __table_args__ = (
        Index(
            "uq_nature_of_flight_description_aircraft_nof_active",
            "aircraft_fk",
            "nature_of_flight",
            unique=True,
            postgresql_where=text("is_deleted IS FALSE"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    nature_of_flight = Column(
        PGEnum(TypeEnum, name="nature_of_flight", create_type=False),
        nullable=False,
        index=True,
    )
    remarks = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)

    aircraft = relationship(
        "Aircraft",
        foreign_keys=[aircraft_fk],
        back_populates="nature_of_flight_descriptions",
    )

    def __repr__(self):
        return (
            f"<NatureOfFlightDescription(id={self.id}, aircraft_fk={self.aircraft_fk}, "
            f"nature_of_flight='{self.nature_of_flight}')>"
        )
