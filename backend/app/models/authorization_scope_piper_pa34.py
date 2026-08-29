from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class AuthorizationScopePiperPa34(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "authorization_scope_piper_pa34"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)

    personnel_authorizations = relationship(
        "PersonnelAuthorization",
        back_populates="authorization_scope_piper_pa34",
    )
    personnel_compliances = relationship(
        "PersonnelCompliance",
        back_populates="authorization_scope_piper_pa34",
    )

    def __repr__(self):
        return f"<AuthorizationScopePiperPa34(id={self.id}, name='{self.name}')>"
