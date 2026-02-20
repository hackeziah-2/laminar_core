from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin


class AccountInformation(Base, TimestampMixin, SoftDeleteMixin):
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

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, index=True)
    
    status = Column(Boolean, default=True, nullable=False, comment="True for active, False for inactive")
    last_login = Column(DateTime(timezone=True), nullable=True)

    role = relationship("Role", back_populates="account_informations")
    user_permissions = relationship(
        "UserPermission",
        back_populates="account_information",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AccountInformation(username='{self.username}', name='{self.first_name} {self.last_name}')>"
