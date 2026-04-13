from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class CertificateCategoryType(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "certificate_category_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)

    organizational_approvals = relationship(
        "OrganizationalApproval",
        back_populates="certificate",
    )

    def __repr__(self):
        return f"<CertificateCategoryType(id={self.id}, name='{self.name}')>"
