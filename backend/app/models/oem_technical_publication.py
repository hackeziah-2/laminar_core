from sqlalchemy import Column, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class OemTechnicalPublication(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "oem_technical_publications"

    id = Column(Integer, primary_key=True, index=True)
    item_fk = Column(
        Integer,
        ForeignKey("oem_item_types.id"),
        nullable=False,
        index=True,
    )
    date_of_expiration = Column(Date, nullable=True)

    item = relationship(
        "OemItemType",
        back_populates="technical_publications",
    )

    def __repr__(self):
        return f"<OemTechnicalPublication(id={self.id}, item_fk={self.item_fk})>"
