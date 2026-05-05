from sqlalchemy import Boolean, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class OrganizationalApproval(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "organizational_approvals"

    id = Column(Integer, primary_key=True, index=True)
    certificate_fk = Column(
        Integer,
        ForeignKey("certificate_category_types.id"),
        nullable=False,
        index=True,
    )
    number = Column(Text, nullable=True)
    date_of_expiration = Column(Date, nullable=True)
    web_link = Column(String(2048), nullable=True)
    file_path = Column(String(500), nullable=True)
    is_withhold = Column(Boolean, default=False, nullable=False)

    certificate = relationship(
        "CertificateCategoryType",
        back_populates="organizational_approvals",
    )

    def __repr__(self):
        return f"<OrganizationalApproval(id={self.id}, certificate_fk={self.certificate_fk}, number='{self.number}')>"
