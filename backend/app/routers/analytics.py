# backend/app/routers/analytics.py
from __future__ import annotations
from typing import Optional, List, Dict, Tuple
from math import ceil, floor
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer, Segment
from ..scoring import compute_health_breakdown

router = APIRouter(prefix="/api/health", tags=["analytics"])

RISK_RED = 60
RISK_GREEN = 80
FACTORS = [
    "login_frequency",
    "feature_adoption",
    "support_ticket_volume",
    "invoice_timeliness",
    "api_usage_trend",
]

@router.get("/summary")
def health_summary(
    segment: Optional[Segment] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns population stats (+ optional segment filter):

    {
      "total": int,
      "healthy": int, "watch": int, "at_risk": int,
      "avg_score": float,
      "avg_factors": {factor -> float},
      "top5": [{"id","name","score"}],
      "bottom5": [{"id","name","score"}]
    }
    """
    q = db.query(Customer)
    if segment:
        q = q.filter(Customer.segment == segment)
    customers: List[Customer] = q.all()
    n = len(customers)
    if n == 0:
        return {
            "total": 0, "healthy": 0, "watch": 0, "at_risk": 0,
            "avg_score": 0.0, "avg_factors": {k: 0.0 for k in FACTORS},
            "top5": [], "bottom5": []
        }

    sums: Dict[str, float] = {k: 0.0 for k in FACTORS}
    sum_total = 0.0
    buckets = {"healthy": 0, "watch": 0, "at_risk": 0}
    ranked: List[Tuple[int, str, float]] = []

    for c in customers:
        b = compute_health_breakdown(db, c.id)
        total = float(b["total"])
        sum_total += total
        for k in FACTORS:
            sums[k] += float(b["factors"].get(k, 0.0))

        if total < RISK_RED:
            buckets["at_risk"] += 1
        elif total < RISK_GREEN:
            buckets["watch"] += 1
        else:
            buckets["healthy"] += 1

        ranked.append((c.id, c.name, total))

    avg_factors = {k: round(sums[k] / n, 2) for k in FACTORS}
    avg_score = round(sum_total / n, 2)

    ranked.sort(key=lambda t: t[2], reverse=True)
    top5 = [{"id": i, "name": name, "score": round(s, 1)} for i, name, s in ranked[:5]]
    bottom5_sorted = sorted(ranked, key=lambda t: t[2])[:5]
    bottom5 = [{"id": i, "name": name, "score": round(s, 1)} for i, name, s in bottom5_sorted]

    return {
        "total": n,
        "healthy": buckets["healthy"],
        "watch": buckets["watch"],
        "at_risk": buckets["at_risk"],
        "avg_score": avg_score,
        "avg_factors": avg_factors,
        "top5": top5,
        "bottom5": bottom5,
    }

def _percentile(sorted_vals: List[float], p: float) -> float:
    """p in [0,1]. Linear interpolation between nearest ranks."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    k = (n - 1) * p
    f, c = floor(k), ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))

@router.get("/trend")
def health_trend(
    days: int = Query(30, ge=1, le=120),
    segment: Optional[Segment] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns an array of daily points for the last `days`:
    [{date: "YYYY-MM-DD", avg: float, p25: float, p75: float}, ...]

    NOTE: This version snapshots *today's* distribution and repeats it
    for each day so the UI always renders. To compute true history,
    make compute_health_breakdown accept an `as_of` datetime and
    re-evaluate factors for each day.
    """
    q = db.query(Customer)
    if segment:
        q = q.filter(Customer.segment == segment)
    customers: List[Customer] = q.all()

    scores: List[float] = []
    for c in customers:
        b = compute_health_breakdown(db, c.id)
        scores.append(float(b["total"]))

    scores.sort()
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    p25 = round(_percentile(scores, 0.25), 2)
    p75 = round(_percentile(scores, 0.75), 2)

    today = date.today()
    out = []
    for i in range(days):
        d = today - timedelta(days=(days - 1 - i))
        out.append({
            "date": d.isoformat(),
            "avg": avg,
            "p25": p25,
            "p75": p75,
        })
    return out