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


def _default_seats(seg: Segment) -> int:
    """
    Assign a realistic seat count by segment.
    Enterprise >> SMB > Startup (rough ranges).
    """
    if seg == Segment.enterprise:
        return randint(200, 1200)
    if seg == Segment.smb:
        return randint(10, 100)
    # startup
    return randint(3, 30)


def seed_if_needed(db: Session):
    """
    Seed ~60 customers with seats and ~90 days of realistic events.

    Guards:
      - If there are already >=50 customers, skip (prevents duplicate seeding).
    """
    if db.query(Customer).count() >= 50:
        return

    # --- Create customers (unique names, deterministic segments, size by segment) ---
    customers = []
    for _ in range(60):
        name = fake.unique.company()           # per-run uniqueness (no dup names in this seeding session)
        seg = _segment_for(name)               # stable segment by name
        c = Customer(
            name=name,
            segment=seg,
            seats=_default_seats(seg),         # size-aware scoring uses this
        )
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
