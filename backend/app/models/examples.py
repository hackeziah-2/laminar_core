from sqlalchemy import Column, Integer, String

from app.database import Base, AuditMixin


class ExampleTable(Base, AuditMixin):
    __tablename__ = "example_table"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
