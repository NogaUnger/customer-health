from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..db import get_db
from .. import models, schemas
from ..scoring import compute_health_breakdown

router = APIRouter(prefix="/api", tags=["customers"])

@router.get("/customers", response_model=List[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    # ensure health_score is current (simple on-demand refresh)
    for c in customers:
        breakdown = compute_health_breakdown(db, c.id)
        c.health_score = breakdown["total"]
    db.commit()
    return customers

@router.get("/customers/{id}/health", response_model=schemas.HealthBreakdown)
def customer_health(id: int, db: Session = Depends(get_db)):
    cust = db.get(models.Customer, id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    breakdown = compute_health_breakdown(db, id)
    cust.health_score = breakdown["total"]
    db.commit()
    return breakdown
