from faker import Faker
from random import choice, random, randint
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Customer, Event, Segment, EventType

fake = Faker()

def seed_if_needed(db: Session):
    if db.query(Customer).count() >= 50:
        return
    segments = [Segment.enterprise, Segment.smb, Segment.startup]

    customers = []
    for _ in range(60):
        c = Customer(
            name=fake.company(),
            segment=choice(segments),
        )
        db.add(c)
        customers.append(c)
    db.commit()

    now = datetime.utcnow()
    for c in customers:
        # 90 days of history
        start = now - timedelta(days=90)
        day = start
        used_features = set()

        while day <= now:
            # logins
            for _ in range(randint(0, 2)):
                db.add(Event(customer_id=c.id, type=EventType.login, ts=day + timedelta(hours=randint(0,23))))

            # feature use
            for _ in range(randint(0, 3)):
                fk = f"feature_{randint(1,10)}"
                used_features.add(fk)
                db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key=fk, ts=day + timedelta(hours=randint(0,23))))

            # api bursts
            if random() < 0.5:
                db.add(Event(customer_id=c.id, type=EventType.api_call, value=randint(20, 500), ts=day + timedelta(hours=randint(0,23))))

            # tickets (some customers at-risk → more tickets)
            if random() < 0.15:
                db.add(Event(customer_id=c.id, type=EventType.support_ticket_opened, ts=day + timedelta(hours=randint(0,23))))

            # invoices monthly
            if day.day == 1:
                if random() < 0.85:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
                else:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))

            day += timedelta(days=1)

    db.commit()
