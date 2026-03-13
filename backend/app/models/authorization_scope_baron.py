from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class AuthorizationScopeBaron(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "authorization_scope_baron"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)

    personnel_authorizations = relationship(
        "PersonnelAuthorization",
        back_populates="authorization_scope_baron",
    )

    def __repr__(self):
        return f"<AuthorizationScopeBaron(id={self.id}, name='{self.name}')>"
