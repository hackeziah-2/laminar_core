from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class AuthorizationScopeOthers(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "authorization_scope_others"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)

    personnel_authorizations = relationship(
        "PersonnelAuthorization",
        back_populates="authorization_scope_others",
    )
    personnel_compliances = relationship(
        "PersonnelCompliance",
        back_populates="authorization_scope_others",
    )

    def __repr__(self):
        return f"<AuthorizationScopeOthers(id={self.id}, name='{self.name}')>"
