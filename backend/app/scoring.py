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

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Event, EventType, Customer, Segment


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ----------------------- segment parameters ----------------------- #
# Targets/penalties tuned per segment. Adjust as you learn from data.
SEGMENT_PARAMS = {
    Segment.enterprise: {
        "login_target_per_seat_30d": 3.0,   # larger orgs: diverse roles, lower per-seat login target
        "ticket_penalty_per_100_seats": 15.0,
    },
    Segment.smb: {
        "login_target_per_seat_30d": 6.0,
        "ticket_penalty_per_100_seats": 20.0,
    },
    Segment.startup: {
        "login_target_per_seat_30d": 6.0,   # agile teams; similar to SMB for monthly cadence
        "ticket_penalty_per_100_seats": 20.0,
    },
}

CORE_FEATURES = 10  # how many core features you track in logs


def _get_ctx(db: Session, customer_id: int) -> tuple[Segment, int]:
    """Fetch segment and seats with safe fallbacks."""
    c: Customer | None = db.get(Customer, customer_id)
    if not c:
        # Let API layer 404 the customer; scoring uses defaults if called directly in tests.
        return Segment.smb, 25
    seg = c.segment
    seats = c.seats or 25
    return seg, max(1, seats)


# ---------------------------- factors ----------------------------- #
def _login_frequency_score(db: Session, customer_id: int, now: datetime, seg: Segment, seats: int) -> float:
    """
    Logins in 30d, normalized by seat count and segment-specific target.

    Score = (logins_30d / (target_per_seat * seats)) * 100, clamped.
    """
    since = now - timedelta(days=30)
    logins = (
        db.query(Event)
        .filter(Event.customer_id == customer_id, Event.type == EventType.login, Event.ts >= since)
        .count()
    )
    target = SEGMENT_PARAMS.get(seg, SEGMENT_PARAMS[Segment.smb])["login_target_per_seat_30d"] * seats
    if target <= 0:
        target = 1.0
    return clamp((logins / target) * 100.0)


def _feature_adoption_score(db: Session, customer_id: int, now: datetime) -> float:
    """
    Distinct features in 30d / CORE_FEATURES.
    Size-agnostic by design: breadth of usage, not volume.
    """
    since = now - timedelta(days=30)
    distinct = (
        db.query(Event.feature_key)
        .filter(
            Event.customer_id == customer_id,
            Event.type == EventType.feature_use,
            Event.ts >= since,
            Event.feature_key.isnot(None),
        )
        .distinct()
        .count()
    )
    return clamp((distinct / CORE_FEATURES) * 100.0)


def _support_ticket_score(db: Session, customer_id: int, now: datetime, seg: Segment, seats: int) -> float:
    """
    Tickets in 30d, normalized per 100 seats, then linear penalty by segment.
    """
    since = now - timedelta(days=30)
    tickets = (
        db.query(Event)
        .filter(Event.customer_id == customer_id, Event.type == EventType.support_ticket_opened, Event.ts >= since)
        .count()
    )
    per_100 = tickets / max(1.0, seats / 100.0)
    penalty = SEGMENT_PARAMS.get(seg, SEGMENT_PARAMS[Segment.smb])["ticket_penalty_per_100_seats"]
    return clamp(100.0 - penalty * per_100)


def _invoice_timeliness_score(db: Session, customer_id: int, now: datetime) -> float:
    """
    Paid vs late in 90d window; neutral 50 if no signal.
    """
    since = now - timedelta(days=90)
    paid = (
        db.query(Event)
        .filter(Event.customer_id == customer_id, Event.type == EventType.invoice_paid, Event.ts >= since)
        .count()
    )
    late = (
        db.query(Event)
        .filter(Event.customer_id == customer_id, Event.type == EventType.invoice_late, Event.ts >= since)
        .count()
    )
    total = paid + late
    if total == 0:
        return 50.0
    return clamp((paid / total) * 100.0)


def _api_usage_trend_score(db: Session, customer_id: int, now: datetime) -> float:
    """
    Ratio-based 7d vs prev 7d; size-agnostic.
    """
    last_7 = now - timedelta(days=7)
    prev_14 = now - timedelta(days=14)

    last = (
        db.query(func.coalesce(func.sum(Event.value), 0))
        .filter(
            Event.customer_id == customer_id,
            Event.type == EventType.api_call,
            Event.ts >= last_7,
            Event.value.isnot(None),
        )
        .scalar()
        or 0
    )

    prev = (
        db.query(func.coalesce(func.sum(Event.value), 0))
        .filter(
            Event.customer_id == customer_id,
            Event.type == EventType.api_call,
            Event.ts < last_7,
            Event.ts >= prev_14,
            Event.value.isnot(None),
        )
        .scalar()
        or 0
    )

    if prev == 0 and last == 0:
        return 50.0
    if prev == 0 and last > 0:
        return 100.0
    if prev > 0 and last == 0:
        return 0.0

    ratio = last / prev
    if ratio >= 1.0:
        return clamp(50.0 + min(50.0, (ratio - 1.0) * 50.0))
    else:
        return clamp(50.0 * ratio)


# ----------------------------- weights ----------------------------- #
# Keep weights consistent across segments for now (you can also vary by seg).
WEIGHTS = {
    "login_frequency": 0.25,
    "feature_adoption": 0.25,
    "support_ticket_volume": 0.20,
    "invoice_timeliness": 0.15,
    "api_usage_trend": 0.15,
}


# ----------------------- public API -------------------------------- #
def compute_health_breakdown(db: Session, customer_id: int, now: datetime | None = None) -> Dict[str, Any]:
    """
    Compute total and per-factor sub-scores with segment/size normalization.
    """
    now = now or datetime.utcnow()
    seg, seats = _get_ctx(db, customer_id)

    factors = {
        "login_frequency": _login_frequency_score(db, customer_id, now, seg, seats),
        "feature_adoption": _feature_adoption_score(db, customer_id, now),
        "support_ticket_volume": _support_ticket_score(db, customer_id, now, seg, seats),
        "invoice_timeliness": _invoice_timeliness_score(db, customer_id, now),
        "api_usage_trend": _api_usage_trend_score(db, customer_id, now),
    }

    total = sum(WEIGHTS[k] * v for k, v in factors.items())
    return {"total": clamp(total), "factors": factors}
