from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Customer, Segment
from ..scoring import compute_health_breakdown

# router = APIRouter(prefix="/api/customers", tags=["customers"])
router = APIRouter(prefix="/customers", tags=["customers"])

# thresholds used in the dashboard
RISK_RED = 60
RISK_GREEN = 80

def risk_bucket(score: float) -> str:
    if score < RISK_RED:
        return "at_risk"
    if score < RISK_GREEN:
        return "watch"
    return "healthy"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("")
def list_customers(
    db: Session = Depends(get_db),
    # pagination
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # optional filters (the UI mostly filters client-side, but having these helps)
    q: Optional[str] = Query(None, description="Search by name (contains)"),
    segment: Optional[Segment] = Query(None),
    risk: Optional[str] = Query(None, pattern="^(at_risk|watch|healthy)$"),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    sort: str = Query("health_score", pattern="^(health_score|name|id)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """
    Returns rows shaped for the dashboard table:
    { id, name, segment, seats, health_score }
    """
    qset = db.query(Customer)
    if segment:
        qset = qset.filter(Customer.segment == segment)
    if q:
        like = f"%{q}%"
        qset = qset.filter(Customer.name.ilike(like))

    customers: List[Customer] = qset.all()

    rows: List[Dict[str, Any]] = []
    for c in customers:
        # compute score on demand so it's always fresh
        bd = compute_health_breakdown(db, c.id)
        rows.append({
            "id": c.id,
            "name": c.name,
            "segment": c.segment.value if hasattr(c.segment, "value") else str(c.segment),
            "seats": c.seats,
            "health_score": round(bd["total"], 2),
        })

    # risk filter (optional)
    if risk:
        rows = [r for r in rows if risk_bucket(r["health_score"]) == risk]

    # score range
    rows = [r for r in rows if min_score <= (r["health_score"] or 0) <= max_score]

    # sort
    def keyer(r):
        if sort == "name":
            return (r["name"] or "").lower()
        return r[sort]
    rows.sort(key=keyer, reverse=(order == "desc"))

    # pagination (after filtering/sorting)
    sliced = rows[offset: offset + limit]
    return sliced

@router.get("/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).get(customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "id": c.id,
        "name": c.name,
        "segment": c.segment.value if hasattr(c.segment, "value") else str(c.segment),
        "seats": c.seats,
    }

@router.get("/{customer_id}/health")
def get_customer_health(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).get(customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    bd = compute_health_breakdown(db, c.id)
    return bd  # {"total": float, "factors": {...}}
