from datetime import datetime, timedelta
from random import random, randint, choice, sample, uniform
from typing import Set

from faker import Faker
from sqlalchemy.orm import Session

from .models import Customer, Event, Segment, EventType

fake = Faker()


def _unique_company_name(db: Session) -> str:
    """Generate a company name that doesn't already exist."""
    for _ in range(50):
        name = fake.company()
        if not db.query(Customer).filter(Customer.name == name).first():
            return name
    # fallback – extremely unlikely to need
    return f"{fake.company()} #{randint(1000,9999)}"


def _seats_for_segment(seg: Segment) -> int:
    if seg == Segment.startup:
        return randint(5, 30)
    if seg == Segment.smb:
        return randint(20, 250)
    return randint(200, 1200)  # enterprise


def _persona_for_segment(seg: Segment) -> str:
    """
    Personas create natural diversity across all factors.
    power: heavy usage, high adoption
    steady: moderate/consistent
    frugal: low usage/adoption
    spiky: bursty API, mixed logins
    churning: low logins, tickets late invoices
    """
    pool = {
        Segment.startup:   ["power", "steady", "frugal", "spiky", "churning"],
        Segment.smb:       ["steady", "power", "spiky", "frugal", "churning"],
        Segment.enterprise:["steady", "power", "spiky", "churning", "frugal"],
    }[seg]
    return choice(pool)


def _persona_params(seg: Segment, seats: int, persona: str):
    """
    Returns a dict of probabilities / rates that control event generation.
    Tuned to avoid saturating any single factor (esp. feature adoption).
    """
    # base probabilities by persona (approx ranges)
    base = {
        "power":    dict(p_login=0.9,  feat_pool=(6, 10), adopt_p=(0.6, 0.95), feat_daily=(1, 3),
                         p_api=0.55, api_amt=(80, 400), p_ticket=0.10, p_paid=0.94),
        "steady":   dict(p_login=0.65, feat_pool=(4, 9),  adopt_p=(0.45, 0.8),  feat_daily=(1, 2),
                         p_api=0.35, api_amt=(40, 220), p_ticket=0.12, p_paid=0.90),
        "spiky":    dict(p_login=0.55, feat_pool=(4, 8),  adopt_p=(0.35, 0.7),  feat_daily=(0, 2),
                         p_api=0.25, api_amt=(120, 600), p_ticket=0.14, p_paid=0.88),
        "frugal":   dict(p_login=0.35, feat_pool=(3, 7),  adopt_p=(0.25, 0.55), feat_daily=(0, 1),
                         p_api=0.15, api_amt=(20, 120),  p_ticket=0.08, p_paid=0.92),
        "churning": dict(p_login=0.18, feat_pool=(2, 6),  adopt_p=(0.15, 0.45), feat_daily=(0, 1),
                         p_api=0.10, api_amt=(10, 80),   p_ticket=0.20, p_paid=0.70),
    }[persona]

    # light segment adjustment: startups explore more features; enterprise files more tickets.
    if seg == Segment.startup:
        base["adopt_p"] = (base["adopt_p"][0] + 0.05, min(0.98, base["adopt_p"][1] + 0.05))
    if seg == Segment.enterprise:
        base["p_ticket"] = min(0.30, base["p_ticket"] + 0.03)

    # seat-based nudge (more seats → more activity)
    size_nudge = 0.0
    if seats >= 200: size_nudge = 0.05
    if seats >= 800: size_nudge = 0.08

    return dict(
        p_login=min(0.98, base["p_login"] + size_nudge/2),
        feat_pool=base["feat_pool"],
        adopt_p=base["adopt_p"],
        feat_daily=base["feat_daily"],
        p_api=min(0.95, base["p_api"] + size_nudge/2),
        api_amt=base["api_amt"],
        p_ticket=base["p_ticket"] + size_nudge/3,
        p_paid=base["p_paid"],
    )


def _choose_features(pool_size: int) -> list[str]:
    return [f"feature_{i}" for i in range(1, pool_size + 1)]


def _adopted_subset(pool: list[str], adopt_prob: float) -> Set[str]:
    """Pick a subset to represent features actually adopted in the last 30 days."""
    # Binomial-like selection per feature (no numpy needed)
    adopted = [f for f in pool if random() < adopt_prob]
    if not adopted:
        adopted = sample(pool, k=1)  # at least one
    return set(adopted)


def seed_if_needed(db: Session):
    # If you want a full reset, drop the DB volume or delete rows before calling this.
    if db.query(Customer).count() >= 50:
        return

    now = datetime.utcnow()
    segments = [Segment.startup, Segment.smb, Segment.enterprise]

    for _ in range(60):
        seg = choice(segments)
        seats = _seats_for_segment(seg)
        c = Customer(name=_unique_company_name(db), segment=seg, seats=seats)
        db.add(c)
        db.flush()  # get c.id without full commit

        persona = _persona_for_segment(seg)
        P = _persona_params(seg, seats, persona)

        # Feature pool & adoption parameters
        pool_size = randint(*P["feat_pool"])            # e.g., 3..10 (varies)
        feature_pool = _choose_features(pool_size)
        adopt_p = uniform(*P["adopt_p"])               # per-company adoption probability
        adopted_last30 = _adopted_subset(feature_pool, adopt_p)

        # Pre-60 days: they might have explored a *different* set as well
        adopt_p_old = max(0.15, adopt_p - 0.15)
        adopted_prev = _adopted_subset(feature_pool, adopt_p_old)

        # Walk 90 days of history
        start = now - timedelta(days=90)
        day = start
        while day <= now:
            days_ago = (now - day).days
            in_last_30 = days_ago <= 30

            # Logins: Bernoulli per day; sometimes 0–2 events sprinkled in the day
            if random() < P["p_login"]:
                for _ in range(randint(0, 2)):
                    db.add(Event(customer_id=c.id, type=EventType.login,
                                 ts=day + timedelta(hours=randint(0, 23))))

            # Feature use:
            #  - last 30 days: only from adopted_last30, with low-to-moderate daily uses
            #  - earlier: from adopted_prev, sometimes sample small random subset (exploration)
            todays_pool = adopted_last30 if in_last_30 else adopted_prev
            if todays_pool:
                uses_today = randint(*P["feat_daily"])  # e.g., 0..2
                if not in_last_30:
                    # exploration: occasionally try a non-adopted feature
                    if random() < 0.2 and len(todays_pool) < len(feature_pool):
                        extra = choice([f for f in feature_pool if f not in todays_pool])
                        todays_pool = set(todays_pool) | {extra}
                for _ in range(uses_today):
                    fk = choice(list(todays_pool))
                    db.add(Event(customer_id=c.id, type=EventType.feature_use,
                                 feature_key=fk, ts=day + timedelta(hours=randint(0, 23))))

            # API bursts (sum counted via 'value')
            if random() < P["p_api"]:
                amount = randint(*P["api_amt"])
                db.add(Event(customer_id=c.id, type=EventType.api_call,
                             value=amount, ts=day + timedelta(hours=randint(0, 23))))

            # Support tickets (at-risk personas have higher volume)
            if random() < P["p_ticket"]:
                db.add(Event(customer_id=c.id, type=EventType.support_ticket_opened,
                             ts=day + timedelta(hours=randint(0, 23))))

            # Invoices: once per month (1st of month), on-time vs late by persona
            if day.day == 1:
                if random() < P["p_paid"]:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
                else:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))

            day += timedelta(days=1)

    db.commit()
