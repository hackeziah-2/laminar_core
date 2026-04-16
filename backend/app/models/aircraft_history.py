from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AircraftHistory(Base):
    __tablename__ = "aircraft_history"

    id = Column(Integer, primary_key=True, index=True)
    aircraft_id = Column(Integer, ForeignKey("aircrafts.id"), nullable=False, index=True)
    field_name = Column(String(255), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(Integer, ForeignKey("account_information.id"), nullable=True, index=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    action_type = Column(String(16), nullable=False, index=True)

    aircraft = relationship("Aircraft", foreign_keys=[aircraft_id])
    changed_by_user = relationship("AccountInformation", foreign_keys=[changed_by])

    @property
    def changed_by_name(self) -> str | None:
        if not self.changed_by_user:
            return None
        return self.changed_by_user.full_name

    def __repr__(self) -> str:
        return (
            f"<AircraftHistory(aircraft_id={self.aircraft_id}, "
            f"field_name='{self.field_name}', action_type='{self.action_type}')>"
        )
