# backend/app/routers/analytics.py
from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer, Segment
from ..scoring import compute_health_breakdown

router = APIRouter(prefix="/api/health", tags=["analytics"])

def _percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    idx = (p / 100.0) * (len(xs) - 1)
    lo = int(idx)
    hi = min(len(xs) - 1, lo + 1)
    w = idx - lo
    return xs[lo] * (1 - w) + xs[hi] * w

@router.get("/trend")
def health_trend(
    days: int = Query(30, ge=7, le=90),
    segment: Optional[Segment] = Query(None),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns daily average/p25/p75 health across customers for the last `days`.
    Format: [{"date":"YYYY-MM-DD","avg":float,"p25":float,"p75":float}, ...]
    """
    now = datetime.utcnow()

    q = db.query(Customer.id)
    if segment:
        q = q.filter(Customer.segment == segment)
    ids = [row.id for row in q.all()]

    out: List[Dict[str, Any]] = []
    for i in range(days, -1, -1):
        ts = now - timedelta(days=i)
        scores: List[float] = []
        for cid in ids:
            scores.append(compute_health_breakdown(db, cid, now=ts)["total"])
        avg = sum(scores) / len(scores) if scores else 0.0
        out.append({
            "date": ts.date().isoformat(),
            "avg": round(avg, 2),
            "p25": round(_percentile(scores, 25), 2) if scores else 0.0,
            "p75": round(_percentile(scores, 75), 2) if scores else 0.0,
        })
    return out
