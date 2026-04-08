from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, AuditMixin


class OrganizationalApprovalHistory(Base, TimestampMixin, AuditMixin):
    __tablename__ = "organizational_approvals_history"

    id = Column(Integer, primary_key=True, index=True)
    certificate_fk = Column(
        Integer,
        ForeignKey("certificate_category_types.id"),
        nullable=False,
        index=True,
    )
    oa_history = Column(
        Integer,
        ForeignKey("organizational_approvals.id"),
        nullable=True,
        index=True,
    )
    number = Column(Text, nullable=True)
    date_of_expiration = Column(Date, nullable=True)
    web_link = Column(String(2048), nullable=True)

    organizational_approval = relationship(
        "OrganizationalApproval",
        foreign_keys=[oa_history],
    )

    def __repr__(self):
        return (
            f"<OrganizationalApprovalHistory(id={self.id}, "
            f"certificate_fk={self.certificate_fk}, oa_history={self.oa_history})>"
        )
