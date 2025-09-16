from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base
import enum

class Segment(str, enum.Enum):
    enterprise = "enterprise"
    smb = "smb"
    startup = "startup"

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    segment = Column(Enum(Segment), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

    # denormalized current health score for fast listing
    health_score = Column(Float, default=0.0)

    events = relationship("Event", back_populates="customer", cascade="all,delete")

class EventType(str, enum.Enum):
    login = "login"
    feature_use = "feature_use"
    api_call = "api_call"
    support_ticket_opened = "support_ticket_opened"
    invoice_paid = "invoice_paid"
    invoice_late = "invoice_late"

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    type = Column(Enum(EventType), nullable=False)
    feature_key = Column(String, nullable=True)
    value = Column(Float, nullable=True)  # e.g., API calls count in a burst
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    customer = relationship("Customer", back_populates="events")
