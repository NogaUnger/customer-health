"""
routers/events.py
=================
Write endpoint for recording customer events that drive health scoring.

Exposes:
- POST /api/customers/{customer_id}/events
"""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/customers", tags=["events"])


@router.post("/{customer_id}/events", response_model=schemas.EventOut, status_code=201)
def create_event(customer_id: int, payload: schemas.EventCreate, db: Session = Depends(get_db)):
    """
    Create a new event for a customer.

    Validation rules:
    - feature_use:    feature_key REQUIRED, value MUST be null
    - api_call:       value REQUIRED (>= 0), feature_key MUST be null
    - login/support/invoice_*: feature_key and value MUST be null

    Returns:
      The created event serialized as EventOut.
    """
    # 1) Ensure the customer exists
    customer = db.get(models.Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    et = payload.type

    # 2) Cross-field validation by type
    if et == models.EventType.feature_use:
        if not payload.feature_key:
            raise HTTPException(status_code=422, detail="feature_key is required for type=feature_use")
        if payload.value is not None:
            raise HTTPException(status_code=422, detail="value must be null for type=feature_use")

    elif et == models.EventType.api_call:
        if payload.value is None:
            raise HTTPException(status_code=422, detail="value is required for type=api_call")
        if payload.value < 0:
            raise HTTPException(status_code=422, detail="value must be >= 0 for type=api_call")
        if payload.feature_key is not None:
            raise HTTPException(status_code=422, detail="feature_key must be null for type=api_call")

    else:
        # login, support_ticket_opened, invoice_paid, invoice_late
        if payload.feature_key is not None:
            raise HTTPException(status_code=422, detail="feature_key must be null for this event type")
        if payload.value is not None:
            raise HTTPException(status_code=422, detail="value must be null for this event type")

    # 3) Persist
    ts = payload.ts or datetime.utcnow()
    ev = models.Event(
        customer_id=customer_id,
        type=et,
        feature_key=payload.feature_key,
        value=payload.value,
        ts=ts,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    return ev
