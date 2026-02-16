import enum
from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class DocumentStatusEnum(str, enum.Enum):
    ACTIVE = "Active"
    EXPIRED = "Expired"
    EXPIRING_SOON = "Expiring Soon"
    INACTIVE = "Inactive"


class DocumentOnBoard(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents_on_board"

    document_id = Column(Integer, primary_key=True, index=True)
    aircraft_id = Column(Integer, ForeignKey("aircrafts.id"), nullable=True, index=True)
    document_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    issue_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    warning_days = Column(Integer, nullable=True, default=30)  # Days before expiry to warn
    status = Column(
        PGEnum(
            "Active",
            "Expired",
            "Expiring Soon",
            "Inactive",
            name="document_status",
            create_type=True,
        ),
        default="Active",
        nullable=False,
    )
    file_path = Column(String(500), nullable=True)
    web_link = Column(String(2048), nullable=True)
    is_aircraft_certificate = Column(Boolean, default=False, nullable=False)

    aircraft = relationship("Aircraft", backref="documents_on_board")

    def __repr__(self):
        return f"<DocumentOnBoard(id={self.document_id}, name='{self.document_name}', aircraft_id={self.aircraft_id})>"
