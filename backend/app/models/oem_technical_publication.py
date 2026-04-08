import enum

from sqlalchemy import Boolean, Column, Integer, Date, String, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class OemTechnicalPublicationCategoryTypeEnum(str, enum.Enum):
    CERTIFICATE = "CERTIFICATE"
    SUBSCRIPTION = "SUBSCRIPTION"
    REGULATORY_CORRESPONDENCE_NON_CERT = "REGULATORY_CORRESPONDENCE_NON_CERT"
    LICENSE = "LICENSE"


class OemTechnicalPublication(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "oem_technical_publications"

    id = Column(Integer, primary_key=True, index=True)
    item_fk = Column(
        Integer,
        ForeignKey("oem_item_types.id"),
        nullable=False,
        index=True,
    )
    category_type = Column(
        PGEnum(
            OemTechnicalPublicationCategoryTypeEnum,
            name="oem_technical_publication_category_type",
            create_type=True,
        ),
        nullable=False,
    )
    date_of_expiration = Column(Date, nullable=True)
    web_link = Column(String(2048), nullable=True)
    is_withhold = Column(Boolean, default=False, nullable=False)

    item = relationship(
        "OemItemType",
        back_populates="technical_publications",
    )

    def __repr__(self):
        return f"<OemTechnicalPublication(id={self.id}, item_fk={self.item_fk}, category_type={self.category_type})>"
