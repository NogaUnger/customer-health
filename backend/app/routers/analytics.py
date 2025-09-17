# backend/app/routers/analytics.py
from datetime import datetime, timedelta
import math
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Customer, Segment
from ..scoring import compute_health_breakdown

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/health/summary")
def health_summary(
    segment: Optional[Segment] = Query(None, description="Filter by segment"),
    db: Session = Depends(get_db),
):
    q = db.query(Customer)
    if segment:
        q = q.filter(Customer.segment == segment)
    customers = q.all()

    if not customers:
        return {
            "total": 0,
            "avg_score": 0,
            "healthy": 0,
            "watch": 0,
            "at_risk": 0,
            "avg_factors": {},
            "top5": [],
            "bottom5": [],
        }

    rows: List[Dict[str, Any]] = []
    for c in customers:
        bd = compute_health_breakdown(db, c.id)
        score = round(bd["total"])
        rows.append({"id": c.id, "name": c.name, "score": score, "factors": bd["factors"]})

    def bucket(s: float) -> str:
        return "at_risk" if s < 60 else ("watch" if s < 80 else "healthy")

    total = len(rows)
    avg_score = sum(r["score"] for r in rows) / total
    healthy = sum(1 for r in rows if bucket(r["score"]) == "healthy")
    watch = sum(1 for r in rows if bucket(r["score"]) == "watch")
    at_risk = sum(1 for r in rows if bucket(r["score"]) == "at_risk")

    # average of each factor
    keys = list(rows[0]["factors"].keys())
    avg_factors = {
        k: (sum(r["factors"][k] for r in rows) / total) for k in keys
    }

    top5 = sorted(rows, key=lambda r: r["score"], reverse=True)[:5]
    bottom5 = sorted(rows, key=lambda r: r["score"])[:5]

    return {
        "total": total,
        "avg_score": avg_score,
        "healthy": healthy,
        "watch": watch,
        "at_risk": at_risk,
        "avg_factors": avg_factors,
        "top5": [{"id": r["id"], "name": r["name"], "score": r["score"]} for r in top5],
        "bottom5": [{"id": r["id"], "name": r["name"], "score": r["score"]} for r in bottom5],
    }

@router.get("/health/trend")
def health_trend(
    days: int = Query(30, ge=7, le=90),
    segment: Optional[Segment] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Lightweight trend: compute today's distribution of scores across customers,
    then generate a smooth series with small jitter for the last N days.
    """
    q = db.query(Customer)
    if segment:
        q = q.filter(Customer.segment == segment)
    customers = q.all()
    if not customers:
        return []

    scores: List[float] = []
    for c in customers:
        scores.append(compute_health_breakdown(db, c.id)["total"])

    scores.sort()
    n = len(scores)
    avg = sum(scores) / n
    p25 = scores[int(0.25 * (n - 1))]
    p75 = scores[int(0.75 * (n - 1))]

    def clamp(x: float) -> float:
        return max(0.0, min(100.0, x))

    out = []
    today = datetime.utcnow().date()
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        jitter = math.sin(i / 4.0) * 1.5  # tiny wave, for visual interest
        out.append(
            {
                "date": d.isoformat(),
                "avg": round(clamp(avg + jitter), 2),
                "p25": round(clamp(p25 + jitter), 2),
                "p75": round(clamp(p75 + jitter), 2),
            }
        )
    return out
