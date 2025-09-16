from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import Customer, Event, Segment, EventType
from app.scoring import compute_health_breakdown

def _new_customer(db):
    c = Customer(name=f'EdgeCo-{datetime.utcnow().timestamp()}', segment=Segment.smb)
    db.add(c); db.commit(); db.refresh(c)
    return c

def test_scoring_trend_up_and_down():
    now = datetime.utcnow()
    with SessionLocal() as db:
        c = _new_customer(db)

        # previous 7 days: 100 calls total
        for d in range(8, 15):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=10, ts=now - timedelta(days=d)))

        # last 7 days: 300 calls total (trend up)
        for d in range(1, 8):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=30, ts=now - timedelta(days=d)))

        # also add a couple of logins + features so other factors are nonzero
        db.add(Event(customer_id=c.id, type=EventType.login, ts=now - timedelta(days=1)))
        db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key="feature_1", ts=now - timedelta(days=2)))
        db.commit()

        up = compute_health_breakdown(db, c.id)
        assert up["factors"]["api_usage_trend"] >= 50

        # flip the trend: last 7 days lower than previous
        for ev in db.query(Event).filter(Event.customer_id == c.id, Event.type == EventType.api_call).all():
            db.delete(ev)
        db.commit()
        # previous 7: high
        for d in range(8, 15):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=30, ts=now - timedelta(days=d)))
        # last 7: low
        for d in range(1, 8):
            db.add(Event(customer_id=c.id, type=EventType.api_call, value=10, ts=now - timedelta(days=d)))
        db.commit()

        down = compute_health_breakdown(db, c.id)
        assert down["factors"]["api_usage_trend"] <= 50
