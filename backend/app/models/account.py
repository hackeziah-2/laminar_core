from sqlalchemy import Column, Integer
from app.database import Base, TimestampMixin, SoftDeleteMixin


class AccountInformation(Base, TimestampMixin, SoftDeleteMixin):
    """Account Information model for referencing pilots and maintenance personnel."""
    __tablename__ = "account_information"

    id = Column(Integer, primary_key=True, index=True)

    def __repr__(self):
        return f"<AccountInformation(id='{self.id}')>"
