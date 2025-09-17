"""
Integration tests for the health-score pipeline via `compute_health_breakdown`.

Scope
-----
These tests write real events into the database and assert that each factor
returned by `compute_health_breakdown(db, customer_id)` moves in the expected
direction:
- login_frequency          → more 30d logins → higher factor
- feature_adoption         → more unique features → higher factor
- support_ticket_volume    → same tickets, more seats → milder penalty → higher factor
- invoice_timeliness       → recent 'late' drags factor down (recency weighting)
- api_usage_trend          → last 7d vs previous 7d: up ≥50, down ≤50
- total                    → many tickets reduce overall total

Design notes
------------
- Each test creates its own customer(s) for isolation.
- Timestamps are relative to `datetime.utcnow()` to clearly fall in the intended windows.
- We only assert *relative* comparisons (>, <, ≥, ≤) to stay stable across minor weight tweaks.

How to run
----------
docker compose run --rm backend pytest -q \
  --cov=app --cov-report=term-missing \
  --cov-config=.coveragerc --cov-fail-under=80
"""

from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import Customer, Event, Segment, EventType
from app.scoring import compute_health_breakdown


def _mk_customer(db, segment=Segment.smb, seats=20) -> Customer:
    """Create a fresh customer with deterministic segment/seat values."""
    c = Customer(name=f"Edge-{datetime.utcnow().timestamp()}", segment=segment, seats=seats)
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_login_frequency_factor_higher_with_more_logins():
    """Customer with more 30d logins should have a higher login_frequency factor."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        low  = _mk_customer(db, seats=20)
        high = _mk_customer(db, seats=20)

        for d in range(1, 5):   # 4 logins in last 30d
            db.add(Event(customer_id=low.id,  type=EventType.login, ts=now - timedelta(days=d)))
        for d in range(1, 16):  # 15 logins in last 30d
            db.add(Event(customer_id=high.id, type=EventType.login, ts=now - timedelta(days=d)))
        db.commit()

        f_low  = compute_health_breakdown(db, low.id )["factors"]["login_frequency"]
        f_high = compute_health_breakdown(db, high.id)["factors"]["login_frequency"]
        assert f_high > f_low


def test_feature_adoption_counts_unique_features():
    """Distinct features—not repeated uses—should raise the adoption factor."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        c = _mk_customer(db)
        # one feature many times
        for _ in range(5):
            db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key="feature_1", ts=now))
        db.commit()
        base = compute_health_breakdown(db, c.id)["factors"]["feature_adoption"]

        # add two distinct features
        db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key="feature_2", ts=now))
        db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key="feature_3", ts=now))
        db.commit()
        more = compute_health_breakdown(db, c.id)["factors"]["feature_adoption"]

        assert more > base


def test_support_ticket_volume_penalty_by_size():
    """Same ticket count: large org penalized less per-100-seats → higher factor."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        small = _mk_customer(db, segment=Segment.startup,   seats=10)
        big   = _mk_customer(db, segment=Segment.enterprise, seats=1000)

        for _ in range(6):
            db.add(Event(customer_id=small.id, type=EventType.support_ticket_opened, ts=now))
            db.add(Event(customer_id=big.id,   type=EventType.support_ticket_opened, ts=now))
        db.commit()

        s = compute_health_breakdown(db, small.id)["factors"]["support_ticket_volume"]
        b = compute_health_breakdown(db, big.id  )["factors"]["support_ticket_volume"]
        assert b > s


def test_invoice_timeliness_recency_weighting():
    """Recent 'late' invoices should reduce the timeliness factor more than old 'late'."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        c = _mk_customer(db)

        # older late, recent paid
        for d in (120, 135, 150):
            db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=now - timedelta(days=d)))
        for d in (5, 15, 25):
            db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=now - timedelta(days=d)))
        db.commit()
        baseline = compute_health_breakdown(db, c.id)["factors"]["invoice_timeliness"]

        # add recent late invoices -> should pull down
        for d in (2, 10):
            db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=now - timedelta(days=d)))
        db.commit()
        worse = compute_health_breakdown(db, c.id)["factors"]["invoice_timeliness"]
        assert worse < baseline


def test_api_usage_trend_up_then_down():
    """Trend ≥50 when last 7d > previous 7d; ≤50 when last 7d < previous 7d."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        c = _mk_customer(db)

        # previous 7 days: low; last 7 days: high
        for d in range(8, 15):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=10, ts=now - timedelta(days=d)))
        for d in range(1, 8):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=30, ts=now - timedelta(days=d)))
        db.commit()
        up = compute_health_breakdown(db, c.id)["factors"]["api_usage_trend"]
        assert up >= 50

        # flip it: previous high; last low
        db.query(Event).filter(Event.customer_id == c.id, Event.type == EventType.api_call).delete()
        db.commit()
        for d in range(8, 15):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=30, ts=now - timedelta(days=d)))
        for d in range(1, 8):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=10, ts=now - timedelta(days=d)))
        db.commit()
        down = compute_health_breakdown(db, c.id)["factors"]["api_usage_trend"]
        assert down <= 50


def test_total_score_drops_with_many_tickets():
    """Overall total should decline when support tickets spike (all else equal)."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        healthy = _mk_customer(db, seats=50)
        risky   = _mk_customer(db, seats=50)

        # baseline engagement + paid invoice to avoid zeros
        for cid in (healthy.id, risky.id):
            db.add(Event(customer_id=cid, type=EventType.login, ts=now - timedelta(days=1)))
            db.add(Event(customer_id=cid, type=EventType.feature_use, feature_key="feature_1", ts=now - timedelta(days=2)))
            db.add(Event(customer_id=cid, type=EventType.invoice_paid, ts=now - timedelta(days=3)))

        # risky gets lots of tickets
        for _ in range(8):
            db.add(Event(customer_id=risky.id, type=EventType.support_ticket_opened, ts=now - timedelta(days=1)))
        db.commit()

        H = compute_health_breakdown(db, healthy.id)["total"]
        R = compute_health_breakdown(db, risky.id  )["total"]
        assert 0 <= H <= 100 and 0 <= R <= 100
        assert R < H
