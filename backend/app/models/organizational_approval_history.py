from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text

from app.database import Base, TimestampMixin


class OrganizationalApprovalHistory(Base, TimestampMixin):
    __tablename__ = "organizational_approvals_history"

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

    def __repr__(self):
        return f"<OrganizationalApprovalHistory(id={self.id}, certificate_fk={self.certificate_fk})>"
