from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["events"])

@router.post("/customers/{id}/events", response_model=schemas.EventOut, status_code=201)
def record_event(id: int, payload: schemas.EventCreate, db: Session = Depends(get_db)):
    cust = db.get(models.Customer, id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    ev = models.Event(
        customer_id=id,
        type=payload.type,
        feature_key=payload.feature_key,
        value=payload.value,
        ts=payload.ts
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev
