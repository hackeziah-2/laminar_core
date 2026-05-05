from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class OemItemType(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "oem_item_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)

    technical_publications = relationship(
        "OemTechnicalPublication",
        back_populates="item",
    )

    def __repr__(self):
        return f"<OemItemType(id={self.id}, name='{self.name}')>"
