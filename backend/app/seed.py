from faker import Faker
from random import random, randint
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Customer, Event, Segment, EventType
import hashlib

fake = Faker()


def _segment_for(name: str) -> Segment:
    """Deterministically map a company name to a segment."""
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)
    return [Segment.enterprise, Segment.smb, Segment.startup][h % 3]


def _default_seats(seg: Segment) -> int:
    """Realistic seat ranges by segment."""
    if seg == Segment.enterprise:
        return randint(200, 1200)
    if seg == Segment.smb:
        return randint(10, 100)
    return randint(3, 30)  # startup


def _pick_profile() -> str:
    """
    Assign a behavior profile:
      - healthy: 30%
      - average: 50%
      - risk:    20%
    """
    r = random()
    if r < 0.30:
        return "healthy"
    if r < 0.80:
        return "average"
    return "risk"


def seed_if_needed(db: Session):
    """Seed ~60 customers with seats and ~90 days of realistic, profiled events."""
    if db.query(Customer).count() >= 50:
        return

    customers = []
    for _ in range(60):
        name = fake.unique.company()
        seg = _segment_for(name)
        c = Customer(
            name=name,
            segment=seg,
            seats=_default_seats(seg),
        )
        # stash a temporary attribute (not persisted) for behavior
        c._profile = _pick_profile()
        db.add(c)
        customers.append(c)

    db.commit()  # assign IDs

    now = datetime.utcnow()
    for c in customers:
        start = now - timedelta(days=90)
        day = start

        # ---------- base rates by segment ----------
        if c.segment == Segment.enterprise:
            base_login_low, base_login_high = 1, 4        # total logins/day
            base_feature_high = 3
            base_api_prob = 0.6
            api_val_low, api_val_high = 120, 700
            ticket_prob = 0.08
        elif c.segment == Segment.smb:
            base_login_low, base_login_high = 0, 3
            base_feature_high = 3
            base_api_prob = 0.5
            api_val_low, api_val_high = 40, 400
            ticket_prob = 0.08
        else:  # startup
            base_login_low, base_login_high = 0, 2
            base_feature_high = 2
            base_api_prob = 0.5
            api_val_low, api_val_high = 25, 300
            ticket_prob = 0.07

        # ---------- profile adjustments ----------
        prof = getattr(c, "_profile", "average")
        if prof == "healthy":
            login_low = max(0, int(base_login_low * 1.3))
            login_high = max(login_low + 1, int(base_login_high * 1.5))
            feature_high = min(4, base_feature_high + 1)
            api_prob = min(0.95, base_api_prob + 0.15)
            paid_prob = 0.95
            ticket_p = max(0.01, ticket_prob * 0.5)
        elif prof == "risk":
            login_low = 0
            login_high = max(1, int(base_login_high * 0.6))
            feature_high = max(1, int(base_feature_high * 0.6))
            api_prob = max(0.05, base_api_prob - 0.25)
            paid_prob = 0.60
            ticket_p = min(0.35, ticket_prob * 2.2)
        else:  # average
            login_low, login_high = base_login_low, base_login_high
            feature_high = base_feature_high
            api_prob = base_api_prob
            paid_prob = 0.85
            ticket_p = ticket_prob

        # ---------- generate 90 days ----------
        while day <= now:
            # logins
            for _ in range(randint(login_low, login_high)):
                db.add(Event(customer_id=c.id, type=EventType.login,
                             ts=day + timedelta(hours=randint(0, 23))))

            # feature use
            for _ in range(randint(0, feature_high)):
                fk = f"feature_{randint(1, 10)}"
                db.add(Event(customer_id=c.id, type=EventType.feature_use, feature_key=fk,
                             ts=day + timedelta(hours=randint(0, 23))))

            # api bursts (slightly bias the last week by profile to influence trend)
            in_last_7 = (now - day).days < 7
            eff_api_prob = api_prob
            if prof == "healthy" and in_last_7:
                eff_api_prob = min(0.98, api_prob + 0.20)
            if prof == "risk" and in_last_7:
                eff_api_prob = max(0.02, api_prob - 0.30)

            if random() < eff_api_prob:
                db.add(Event(customer_id=c.id, type=EventType.api_call,
                             value=randint(api_val_low, api_val_high),
                             ts=day + timedelta(hours=randint(0, 23))))

            # tickets
            if random() < ticket_p:
                db.add(Event(customer_id=c.id, type=EventType.support_ticket_opened,
                             ts=day + timedelta(hours=randint(0, 23))))

            # ---- invoices (monthly with jitter) ----
# Allow a single monthly invoice around day 1 ±2 days.
# Also, with a small chance, emit an off-cycle invoice mid-month.
if 'last_invoice_month' not in locals():
    last_invoice_month = None
    offcycle_emitted = set()

month_key = (day.year, day.month)

# monthly invoice once per month (around the 1st, ±2 days)
if last_invoice_month != month_key and day.day in (30, 31, 1, 2, 3):
    # jitter chance: only issue once per month
    issue = False
    if day.day == 1:
        issue = True
    elif day.day in (30, 31, 2, 3) and random() < 0.35:
        issue = True

    if issue:
        # slight jitter to paid probability per invoice
        jitter = (random() - 0.5) * 0.20  # ±0.10
        this_paid_prob = max(0.05, min(0.99, paid_prob + jitter))
        if random() < this_paid_prob:
            db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
        else:
            db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))
        last_invoice_month = month_key

    # off-cycle invoice (rare, mid-month)
    if 14 <= day.day <= 16 and month_key not in offcycle_emitted and random() < 0.15:
        jitter = (random() - 0.5) * 0.20
        this_paid_prob = max(0.05, min(0.99, paid_prob + jitter))
        if random() < this_paid_prob:
            db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
        else:
            db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))
        offcycle_emitted.add(month_key)


    day += timedelta(days=1)

    # cleanup temp
    delattr(c, "_profile")

    db.commit()

    try:
        fake.unique.clear()
    except Exception:
        pass
