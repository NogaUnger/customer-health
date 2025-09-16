from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Segment(str, Enum):
    enterprise = "enterprise"
    smb = "smb"
    startup = "startup"

class EventType(str, Enum):
    login = "login"
    feature_use = "feature_use"
    api_call = "api_call"
    support_ticket_opened = "support_ticket_opened"
    invoice_paid = "invoice_paid"
    invoice_late = "invoice_late"

class EventCreate(BaseModel):
    type: EventType
    feature_key: Optional[str] = None
    value: Optional[float] = None
    ts: Optional[datetime] = None

class EventOut(EventCreate):
    id: int
    customer_id: int
    ts: datetime
    model_config = ConfigDict(from_attributes=True)

class CustomerBase(BaseModel):
    name: str
    segment: Segment

class CustomerOut(BaseModel):
    name: str
    segment: Segment
    id: int
    health_score: float = Field(0, ge=0, le=100)
    model_config = ConfigDict(from_attributes=True)

class HealthBreakdown(BaseModel):
    total: float
    factors: dict
