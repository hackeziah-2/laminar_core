from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class AtlBatch(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "atl_batch"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    atl_logs = relationship(
        "AircraftTechnicalLog",
        back_populates="atl_batch",
    )

    def __repr__(self):
        return f"<AtlBatch(id={self.id}, name={self.name!r})>"
