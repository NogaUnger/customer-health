# backend/app/routers/customers.py
from __future__ import annotations

from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from ..db import get_db
from ..models import Customer, Segment
from ..scoring import compute_health_breakdown

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("")
def list_customers(
    db: Session = Depends(get_db),
    # used by your dashboard's initial “fetch all” loop
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # optional (kept for completeness if you call them elsewhere)
    q: Optional[str] = Query(None, description="Case-insensitive substring on name"),
    segment: Optional[Segment] = Query(None),
    sort: Literal["id", "name", "health_score"] = "id",
    order: Literal["asc", "desc"] = "asc",
) -> List[dict]:
    """
    Returns a page of customers with a computed health score.

    Response item shape:
      { id, name, segment, seats, health_score }
    """
    query = db.query(Customer)

    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%"))
    if segment:
        query = query.filter(Customer.segment == segment)

    # For stable pagination, sort at DB level when possible.
    if sort in ("id", "name"):
        direction = asc if order == "asc" else desc
        col = Customer.id if sort == "id" else Customer.name
        query = query.order_by(direction(col))
        customers = query.offset(offset).limit(limit).all()
        results = []
        for c in customers:
            score = compute_health_breakdown(db, c.id)["total"]
            results.append({
                "id": c.id,
                "name": c.name,
                "segment": c.segment.value if hasattr(c.segment, "value") else c.segment,
                "seats": c.seats,  # <-- company size
                "health_score": score,
            })
        return results

    # sort == "health_score": compute then sort in Python
    customers = query.offset(offset).limit(limit).all()
    items = []
    for c in customers:
        score = compute_health_breakdown(db, c.id)["total"]
        items.append({
            "id": c.id,
            "name": c.name,
            "segment": c.segment.value if hasattr(c.segment, "value") else c.segment,
            "seats": c.seats,
            "health_score": score,
        })
    items.sort(key=lambda r: (r["health_score"] is None, r["health_score"]))
    if order == "desc":
        items.reverse()
    return items


@router.get("/{customer_id}/health")
def customer_health(customer_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Return the health breakdown for a single customer.
    Shape: {"total": float, "factors": {...}}
    """
    c = db.query(Customer).get(customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        return compute_health_breakdown(db, customer_id)
    except Exception as e:
        # Harden against any unexpected scoring edge cases
        raise HTTPException(status_code=500, detail=f"Health computation failed: {e}")