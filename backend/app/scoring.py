"""
scoring.py
==========
Segment/size-aware scoring: 0–100 health with explainable factors.

Research-backed design:
- Login frequency (30d) → engagement. Normalize by seats and segment targets.
- Feature breadth (30d) → value breadth. Size-agnostic (share of core features).
- Support tickets (30d) → friction. Normalize per 100 seats.
- Invoice timeliness (90d) → commercial risk. Paid vs late ratio.
- API usage trend (7d vs prev 7d) → short-term momentum (ratio-based).

All factors return 0..100. WEIGHTS sum to 1.0.
"""

# backend/app/scoring.py
from __future__ import annotations

from datetime import datetime, timedelta
from math import log2
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Customer, Event, EventType, Segment


# ---------- utilities ----------

def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a numeric value to [lo, hi]."""
    return max(lo, min(hi, float(x)))


# Segment-specific assumptions (targets/penalties can be tuned)
SEGMENT_PARAMS: Dict[Segment, Dict[str, float]] = {
    Segment.enterprise: {"login_target_per_seat_30d": 0.15, "ticket_penalty_per_100_seats": 16.0},
    Segment.smb:        {"login_target_per_seat_30d": 0.80, "ticket_penalty_per_100_seats": 10.0},
    Segment.startup:    {"login_target_per_seat_30d": 1.20, "ticket_penalty_per_100_seats": 10.0},
}

# Overall factor weights (sum to 1.0)
WEIGHTS = {
    "login_frequency":       0.25,
    "feature_adoption":      0.20,
    "support_ticket_volume": 0.25,
    "invoice_timeliness":    0.20,
    "api_usage_trend":       0.10,
}


# ---------- pure scoring helpers (UNIT-TESTED) ----------

def score_login_frequency(total_logins_30d: int, seats: int | None, segment: Segment) -> float:
    """
    Normalize login activity by org size & segment target.
    target_total = seats * target_per_seat_30d
    score = 100 * (total / target_total) capped to [0,100]
    """
    seats_eff = max(1, int(seats or 1))
    target_per_seat = SEGMENT_PARAMS[segment]["login_target_per_seat_30d"]
    target_total = seats_eff * target_per_seat
    if target_total <= 0:
        return 50.0  # neutral fallback
    return clamp(100.0 * (float(total_logins_30d) / float(target_total)))


def score_feature_adoption(unique_features_30d: int) -> float:
    """
    Map count of distinct features used in 30d to 0..100.
    Using a soft target of 6 distinct features → 100.
    """
    target = 6.0
    return clamp(100.0 * (float(unique_features_30d) / target))


def score_support_ticket_volume(tickets_30d: int, seats: int | None, segment: Segment) -> float:
    """
    Penalize by tickets per 100 seats (bigger orgs absorb more volume).
    score = 100 - (tickets_per_100 * penalty_unit)
    """
    seats_eff = max(1, int(seats or 1))
    per_100 = max(1.0, seats_eff / 100.0)
    tickets_per_100 = float(tickets_30d) / per_100
    penalty_unit = SEGMENT_PARAMS[segment]["ticket_penalty_per_100_seats"]
    return clamp(100.0 - (tickets_per_100 * penalty_unit))


def score_invoice_timeliness(invoices: List[Tuple[str, datetime]]) -> float:
    """
    Recency-weighted paid ratio over ~180 days.
    invoices: list of (event_type, ts) where event_type in {"invoice_paid","invoice_late"}.
    Recent events weigh more; we use linear decay with a small floor.
    """
    if not invoices:
        return 60.0  # mildly positive neutral without data
    now = datetime.utcnow()
    horizon_days = 180.0

    w_paid = 0.0
    w_total = 0.0
    for ev_type, ts in invoices:
        age = max(0.0, (now - ts).days)
        w = max(0.1, 1.0 - (age / horizon_days))  # 0.1 floor so old items still count a bit
        w_total += w
        if ev_type == "invoice_paid":
            w_paid += w
    if w_total <= 0:
        return 60.0
    return clamp(100.0 * (w_paid / w_total))


def score_api_usage_trend(recent_sum: float, prev_sum: float) -> float:
    """
    Compare last 7 days vs previous 7 days. 50 = neutral.
    Use log2 mapping so ratios compress nicely:
      ratio=1 → 50, 2x → ~75, 4x → ~100, 0.5x → ~25.
    """
    if prev_sum <= 0 and recent_sum <= 0:
        return 50.0
    if prev_sum <= 0 < recent_sum:
        return 85.0  # strong positive if we had nothing then some usage
    ratio = max(1e-9, float(recent_sum)) / max(1e-9, float(prev_sum))
    score = 50.0 + 25.0 * log2(ratio)
    return clamp(score)


# ---------- DB-backed breakdown (INTEGRATION-TESTED) ----------

def compute_health_breakdown(
    db: Session,
    customer_id: int,
    now: datetime | None = None,   # <-- new optional parameter
) -> Dict[str, float | Dict[str, float]]:
    """Compute factors & total; if `now` is provided, windows are relative to it."""
    if now is None:
        now = datetime.utcnow()

    c: Customer | None = db.query(Customer).get(customer_id)
    if not c:
        return {"total": 0.0, "factors": {k: 0.0 for k in WEIGHTS}}

    d30  = now - timedelta(days=30)
    d7   = now - timedelta(days=7)
    d14  = now - timedelta(days=14)
    d180 = now - timedelta(days=180)

    # 30d logins
    total_logins_30d = db.query(func.count(Event.id)).filter(
        Event.customer_id == c.id, Event.type == EventType.login, Event.ts >= d30
    ).scalar() or 0

    # 30d unique features
    unique_features_30d = db.query(func.count(func.distinct(Event.feature_key))).filter(
        Event.customer_id == c.id, Event.type == EventType.feature_use, Event.ts >= d30
    ).scalar() or 0

    # 30d tickets
    tickets_30d = db.query(func.count(Event.id)).filter(
        Event.customer_id == c.id, Event.type == EventType.support_ticket_opened, Event.ts >= d30
    ).scalar() or 0

    # 180d invoices (type + ts)
    inv_rows = db.query(Event.type, Event.ts).filter(
        Event.customer_id == c.id,
        Event.type.in_([EventType.invoice_paid, EventType.invoice_late]),
        Event.ts >= d180
    ).all()
    invoices = [("invoice_paid" if t == EventType.invoice_paid else "invoice_late", ts) for (t, ts) in inv_rows]

    # API usage sums
    recent_sum = db.query(func.coalesce(func.sum(Event.value), 0)).filter(
        Event.customer_id == c.id, Event.type == EventType.api_call, Event.ts >= d7
    ).scalar() or 0
    prev_sum = db.query(func.coalesce(func.sum(Event.value), 0)).filter(
        Event.customer_id == c.id, Event.type == EventType.api_call, Event.ts >= d14, Event.ts < d7
    ).scalar() or 0

    factors = {
        "login_frequency":       score_login_frequency(int(total_logins_30d), c.seats, c.segment),
        "feature_adoption":      score_feature_adoption(int(unique_features_30d)),
        "support_ticket_volume": score_support_ticket_volume(int(tickets_30d), c.seats, c.segment),
        "invoice_timeliness":    score_invoice_timeliness(invoices),
        "api_usage_trend":       score_api_usage_trend(float(recent_sum), float(prev_sum)),
    }
    total = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
    return {"total": clamp(total), "factors": factors}
