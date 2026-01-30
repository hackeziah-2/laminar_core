from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base, TimestampMixin, SoftDeleteMixin


class AccountInformation(Base, TimestampMixin, SoftDeleteMixin):
    """Account Information model for referencing pilots and maintenance personnel."""
    __tablename__ = "account_information"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    middle_name = Column(String(100), nullable=True)
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    
    designation = Column(String(100), nullable=True)
    license_no = Column(String(100), nullable=True, index=True)
    auth_stamp = Column(String(255), nullable=True)
    
    status = Column(Boolean, default=True, nullable=False, comment="True for active, False for inactive")

    def __repr__(self):
        return f"<AccountInformation(username='{self.username}', name='{self.first_name} {self.last_name}')>"
