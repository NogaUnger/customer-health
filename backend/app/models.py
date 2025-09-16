"""
models.py
=========
ORM models and enums for the Customer Health API.

- Segment:          enterprise | smb | startup
- EventType:        login | feature_use | api_call | support_ticket_opened | invoice_paid | invoice_late
- Customer:         companies we score (denormalized `health_score` for fast listing)
- Event:            time-stamped activity for customers (drives scoring)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class Segment(PyEnum):
    """Customer segment taxonomy (kept intentionally simple)."""
    enterprise = "enterprise"
    smb = "smb"
    startup = "startup"


class EventType(PyEnum):
    """Kinds of events that affect health scoring."""
    login = "login"
    feature_use = "feature_use"
    api_call = "api_call"
    support_ticket_opened = "support_ticket_opened"
    invoice_paid = "invoice_paid"
    invoice_late = "invoice_late"


# -----------------------------------------------------------------------------
# Customer
# -----------------------------------------------------------------------------
class Customer(Base):
    """
    Customers (tenants/accounts) we compute health for.

    Notes:
    - `health_score` is denormalized here so listing customers is O(1) per row.
      We recompute+persist it when /api/customers or /api/customers/{id}/health are called.
    - A DB-level unique constraint on `name` ensures we don't insert duplicates.
    """
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_customers_name"),
        Index("ix_customers_segment", "segment"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    segment = Column(Enum(Segment), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    # denormalized total (0..100)
    health_score = Column(Float, default=0.0, nullable=False)

    # relationship to events
    events = relationship(
        "Event",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# -----------------------------------------------------------------------------
# Event
# -----------------------------------------------------------------------------
class Event(Base):
    """
    Raw activity that drives health scoring.

    Conventions (validated at the API layer, not enforced by the DB):
    - type == feature_use  => feature_key must be set
    - type == api_call     => value (int >= 0) should be set
    - invoice_paid/late    => represent monthly billing outcomes
    """
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_customer_ts", "customer_id", "ts"),
        Index("ix_events_type_ts", "type", "ts"),
    )

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(EventType), nullable=False)

    # Optional fields depending on event type:
    feature_key = Column(String, nullable=True)   # used for feature_use
    value = Column(Integer, nullable=True)        # used for api_call (e.g., number of calls in a burst)

    ts = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    customer = relationship("Customer", back_populates="events")
