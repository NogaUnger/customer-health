"""
routers/customers.py
====================
Endpoints for listing customers and fetching a single customer's health breakdown.

Exposes:
- GET /api/customers
- GET /api/customers/{id}/health
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas, scoring

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    """
    Return all customers with their *current* health_score.

    Flow:
      1) Load all customers (ordered by id for stable output).
      2) For each customer, recompute health using recent events (scoring.py).
      3) Persist the latest total back into Customer.health_score (denormalized).
      4) Commit once, then return the list serialized via schemas.CustomerOut.
    """
    customers = (
        db.query(models.Customer)
        .order_by(models.Customer.id.asc())
        .all()
    )

    for c in customers:
        breakdown = scoring.compute_health_breakdown(db, c.id)
        c.health_score = breakdown["total"]
        # add back to session so SQLAlchemy knows it changed
        db.add(c)

    db.commit()
    return customers


@router.get("/{customer_id}/health", response_model=schemas.HealthBreakdown)
def get_customer_health(customer_id: int, db: Session = Depends(get_db)):
    """
    Return a detailed health breakdown for a single customer (0–100 total + per-factor scores).

    Flow:
      1) Ensure the customer exists (404 if not).
      2) Compute the breakdown with scoring.compute_health_breakdown.
      3) Persist the total back into Customer.health_score (keep list endpoint fast).
      4) Commit and return the breakdown (Pydantic schema does the JSON).
    """
    customer = db.get(models.Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    breakdown = scoring.compute_health_breakdown(db, customer_id)
    customer.health_score = breakdown["total"]
    db.add(customer)
    db.commit()

    return breakdown
