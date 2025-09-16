from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .models import Customer, Event, EventType

# We compute a 0–100 score from weighted sub-scores.
WEIGHTS = {
    "login_frequency": 0.25,
    "feature_adoption": 0.25,
    "support_ticket_volume": 0.20,
    "invoice_timeliness": 0.15,
    "api_usage_trend": 0.15,
}

def clamp(x, lo=0.0, hi=100.0): 
    return max(lo, min(hi, x))

def _login_frequency(db: Session, customer_id: int) -> float:
    # last 30 days: 20+ logins ⇒ 100; 0 ⇒ 0 (linear)
    since = datetime.utcnow() - timedelta(days=30)
    count = db.query(func.count(Event.id)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.login,
             Event.ts >= since)
    ).scalar() or 0
    return clamp(min(count, 20) / 20 * 100)

def _feature_adoption(db: Session, customer_id: int) -> float:
    # number of distinct features used in last 30d; 6+ ⇒ 100
    since = datetime.utcnow() - timedelta(days=30)
    distinct = db.query(Event.feature_key).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.feature_use,
             Event.ts >= since,
             Event.feature_key.isnot(None))
    ).distinct().count()
    return clamp(min(distinct, 6) / 6 * 100)

def _support_ticket_volume(db: Session, customer_id: int) -> float:
    # more tickets => lower score; 0 tickets=100; 6+ tickets=0
    since = datetime.utcnow() - timedelta(days=30)
    tickets = db.query(func.count(Event.id)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.support_ticket_opened,
             Event.ts >= since)
    ).scalar() or 0
    return clamp(100 - min(tickets, 6) / 6 * 100)

def _invoice_timeliness(db: Session, customer_id: int) -> float:
    # invoice_paid adds, invoice_late subtracts; map to 0–100
    since = datetime.utcnow() - timedelta(days=90)
    paid = db.query(func.count(Event.id)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.invoice_paid,
             Event.ts >= since)
    ).scalar() or 0
    late = db.query(func.count(Event.id)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.invoice_late,
             Event.ts >= since)
    ).scalar() or 0
    raw = 70 + 15*min(paid, 2) - 25*min(late, 2)
    return clamp(raw)

def _api_usage_trend(db: Session, customer_id: int) -> float:
    # simplistic trend: last 7d vs previous 7d api_call totals
    now = datetime.utcnow()
    w1 = db.query(func.sum(Event.value)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.api_call,
             Event.ts >= now - timedelta(days=7))
    ).scalar() or 0
    w0 = db.query(func.sum(Event.value)).filter(
        and_(Event.customer_id == customer_id,
             Event.type == EventType.api_call,
             Event.ts <  now - timedelta(days=7),
             Event.ts >= now - timedelta(days=14))
    ).scalar() or 0
    if w0 == 0 and w1 == 0:
        return 50.0
    if w0 == 0 and w1 > 0:
        return 100.0
    change = (w1 - w0) / max(w0, 1)
    # map change: -100% ⇒ 0, 0% ⇒ 60, +100% ⇒ 100 (clamped)
    score = 60 + 40 * max(-1.0, min(1.0, change))
    return clamp(score)

def compute_health_breakdown(db: Session, customer_id: int) -> dict:
    pieces = {
        "login_frequency": _login_frequency(db, customer_id),
        "feature_adoption": _feature_adoption(db, customer_id),
        "support_ticket_volume": _support_ticket_volume(db, customer_id),
        "invoice_timeliness": _invoice_timeliness(db, customer_id),
        "api_usage_trend": _api_usage_trend(db, customer_id),
    }
    total = sum(pieces[k] * WEIGHTS[k] for k in pieces)
    return {"total": round(total, 2), "factors": pieces}
