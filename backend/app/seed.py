from faker import Faker
from random import random, randint
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Customer, Event, Segment, EventType
import hashlib

fake = Faker()


def _segment_for(name: str) -> Segment:
    """
    Deterministically map a company name to a segment.
    Same name => same segment (stable across runs).
    """
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)
    return [Segment.enterprise, Segment.smb, Segment.startup][h % 3]


def seed_if_needed(db: Session):
    """
    Seed ~60 customers with ~90 days of realistic events.
    - Ensures unique company names per run (Faker.unique).
    - Ensures segment is deterministic by name (no same-name/different-segment issue).
    - Skips seeding if there are already >= 50 customers.
    """
    # Don't reseed if we already have a decent dataset
    if db.query(Customer).count() >= 50:
        return

    # --- Create customers (unique names, deterministic segments) ---
    customers = []
    for _ in range(60):
        name = fake.unique.company()          # per-run uniqueness
        seg = _segment_for(name)              # stable segment assignment
        c = Customer(name=name, segment=seg)
        db.add(c)
        customers.append(c)

    db.commit()  # assign IDs

    # --- Generate ~90 days of history for each customer ---
    now = datetime.utcnow()
    for c in customers:
        start = now - timedelta(days=90)
        day = start

        while day <= now:
            # Logins: 0–2 per day
            for _ in range(randint(0, 2)):
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.login,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # Feature use: 0–3 per day across 10 possible features
            for _ in range(randint(0, 3)):
                fk = f"feature_{randint(1, 10)}"
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.feature_use,
                        feature_key=fk,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # API usage bursts: ~50% of days
            if random() < 0.5:
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.api_call,
                        value=randint(20, 500),
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # Support tickets: ~15% chance per day
            if random() < 0.15:
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.support_ticket_opened,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # Invoices on the 1st of the month: 85% paid, 15% late
            if day.day == 1:
                if random() < 0.85:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
                else:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))

            day += timedelta(days=1)

    db.commit()

    # Clear Faker's uniqueness cache (safe if called again in this process)
    try:
        fake.unique.clear()
    except Exception:
        pass
