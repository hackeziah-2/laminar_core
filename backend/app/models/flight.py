from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin, SoftDeleteMixin
import datetime
from sqlalchemy import Column, Enum, String
from enum import Enum as PyEnum

class FlightStatus(PyEnum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    CANCELLED = "cancelled"

class Flight(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "flights"
    id = Column(Integer, primary_key=True, index=True)
    flight_no = Column(String(50), nullable=False, index=True)
    origin = Column(String(100), nullable=False, index=True)
    destination = Column(String(100), nullable=False, index=True)
    departure_time = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    arrival_time = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    status = Column(Enum(FlightStatus), default=FlightStatus.SCHEDULED)
