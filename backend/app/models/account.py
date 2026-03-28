from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class AccountInformation(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Account Information model for referencing pilots and maintenance personnel."""
    __tablename__ = "account_information"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    middle_name = Column(String(100), nullable=True)
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=True, index=True)
    password = Column(String(255), nullable=False)
    
    designation = Column(String(100), nullable=True)
    license_no = Column(String(100), nullable=True, index=True)
    auth_stamp = Column(String(255), nullable=True)
    auth_initial_doi = Column(Date, nullable=True)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, index=True)
    
    status = Column(Boolean, default=True, nullable=False, comment="True for active, False for inactive")
    last_login = Column(DateTime(timezone=True), nullable=True)

    role = relationship(
        "Role",
        foreign_keys=[role_id],
        back_populates="account_informations",
    )
    user_permissions = relationship(
        "UserPermission",
        foreign_keys="[UserPermission.account_id]",
        back_populates="account_information",
        cascade="all, delete-orphan",
    )
    personnel_authorizations = relationship(
        "PersonnelAuthorization",
        foreign_keys="[PersonnelAuthorization.account_information_id]",
        back_populates="account_information",
    )
    personnel_compliances = relationship(
        "PersonnelCompliance",
        foreign_keys="[PersonnelCompliance.account_information_id]",
        back_populates="account_information",
    )

    def __repr__(self):
        return f"<AccountInformation(username='{self.username}', name='{self.first_name} {self.last_name}')>"

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()