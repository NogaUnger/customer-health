from faker import Faker
from random import random, randint
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Customer, Event, Segment, EventType
import hashlib

fake = Faker()


def _segment_for(name: str) -> Segment:
    """Deterministically map a company name to a segment so the same
    name always lands in the same segment."""
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)
    return [Segment.enterprise, Segment.smb, Segment.startup][h % 3]


def _default_seats(seg: Segment) -> int:
    """Rough but realistic seat ranges by segment."""
    if seg == Segment.enterprise:
        return randint(200, 1200)
    if seg == Segment.smb:
        return randint(10, 100)
    return randint(3, 30)  # startup


def _pick_profile() -> str:
    """
    Assign a behavior profile to shape activity/health:
      - healthy: 25%
      - average: 45%
      - risk   : 30%  (a bit higher to ensure visible at-risk cohort)
    """
    r = random()
    if r < 0.25:
        return "healthy"
    if r < 0.70:
        return "average"
    return "risk"


def seed_if_needed(db: Session):
    """
    Seed ~60 customers with seats and ~120 days of realistic, profiled events.

    Guard:
      - If there are already >= 50 customers, skip (prevents duplicate seeding).
    """
    if db.query(Customer).count() >= 50:
        return

    # -------- create customers (unique names, deterministic segment, seats) --------
    customers: list[Customer] = []
    for _ in range(60):
        name = fake.unique.company()
        seg = _segment_for(name)
        c = Customer(
            name=name,
            segment=seg,
            seats=_default_seats(seg),
        )
        # temp attribute (not persisted) to drive behavior during seeding
        c._profile = _pick_profile()
        db.add(c)
        customers.append(c)

    db.commit()  # assign IDs

    # -------- generate ~120 days of history per customer --------
    now = datetime.utcnow()
    for c in customers:
        start = now - timedelta(days=120)  # more months → smoother invoice timeliness
        day = start

        # ----- base rates by segment (total events per day, not per-seat) -----
        if c.segment == Segment.enterprise:
            base_login_low, base_login_high = 1, 4
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

        # ----- profile adjustments (healthy / average / risk) -----
        prof = getattr(c, "_profile", "average")
        if prof == "healthy":
            login_low = max(0, int(base_login_low * 1.3))
            login_high = max(login_low + 1, int(base_login_high * 1.5))
            feature_high = min(4, base_feature_high + 1)
            api_prob = min(0.95, base_api_prob + 0.15)
            paid_prob = 0.95
            ticket_p = max(0.01, ticket_prob * 0.5)
        elif prof == "risk":
            # make risk clearly risky
            login_low = 0
            login_high = max(1, int(base_login_high * 0.4))         # fewer logins overall
            feature_high = 1                                         # almost no breadth
            api_prob = max(0.02, base_api_prob - 0.35)              # fewer API bursts
            paid_prob = 0.35                                         # many late invoices
            ticket_p = min(0.60, ticket_prob * 3.0)                  # much more ticket pressure
        else:  # average
            login_low, login_high = base_login_low, base_login_high
            feature_high = base_feature_high
            api_prob = base_api_prob
            paid_prob = 0.85
            ticket_p = ticket_prob

        # ----- per-customer invoice state -----
        last_invoice_month: tuple[int, int] | None = None  # (year, month) last monthly invoice issued
        offcycle_emitted: set[tuple[int, int]] = set()     # months with off-cycle invoice already issued

        # ----- daily loop -----
        while day <= now:
            # logins
            for _ in range(randint(login_low, login_high)):
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.login,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # feature use (distinct features across 1..10)
            for _ in range(randint(0, feature_high)):
                fk = f"feature_{randint(1, 10)}"
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.feature_use,
                        feature_key=fk,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # api bursts: profile influences the last week trend
            in_last_7 = (now - day).days < 7
            eff_api_prob = api_prob
            if prof == "healthy" and in_last_7:
                eff_api_prob = min(0.98, api_prob + 0.20)
            if prof == "risk" and in_last_7:
                eff_api_prob = max(0.01, api_prob - 0.35)  # sharper recent slump

            if random() < eff_api_prob:
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.api_call,
                        value=randint(api_val_low, api_val_high),
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # tickets: baseline + extra recent pressure for risk
            if random() < ticket_p:
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.support_ticket_opened,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )
            # extra recent tickets for risk in last 14 days
            if prof == "risk" and (now - day).days < 14 and random() < 0.15:
                db.add(
                    Event(
                        customer_id=c.id,
                        type=EventType.support_ticket_opened,
                        ts=day + timedelta(hours=randint(0, 23)),
                    )
                )

            # ---- invoices (monthly with jitter + rare off-cycle) ----
            month_key = (day.year, day.month)

            # monthly invoice once per month (around the 1st, ±2 days)
            if last_invoice_month != month_key and day.day in (30, 31, 1, 2, 3):
                issue = False
                if day.day == 1:
                    issue = True
                elif day.day in (30, 31, 2, 3) and random() < 0.35:
                    issue = True

                if issue:
                    # slight jitter on the per-invoice paid probability
                    jitter = (random() - 0.5) * 0.20  # ±0.10
                    this_paid_prob = max(0.05, min(0.99, paid_prob + jitter))

                    # for risk accounts, skew recent invoices toward "late"
                    if prof == "risk" and (now - day).days <= 60:
                        this_paid_prob = max(0.05, min(0.60, this_paid_prob - 0.25))

                    if random() < this_paid_prob:
                        db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
                    else:
                        db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))
                    last_invoice_month = month_key

            # off-cycle invoice (rare, mid-month; one per month max)
            if 14 <= day.day <= 16 and month_key not in offcycle_emitted and random() < 0.15:
                jitter = (random() - 0.5) * 0.20
                this_paid_prob = max(0.05, min(0.99, paid_prob + jitter))
                if prof == "risk" and (now - day).days <= 60:
                    this_paid_prob = max(0.05, min(0.60, this_paid_prob - 0.25))

                if random() < this_paid_prob:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_paid, ts=day))
                else:
                    db.add(Event(customer_id=c.id, type=EventType.invoice_late, ts=day))
                offcycle_emitted.add(month_key)

            day += timedelta(days=1)

        # cleanup temporary attribute
        if hasattr(c, "_profile"):
            delattr(c, "_profile")

    db.commit()

    # clear Faker's uniqueness cache for safety if called again
    try:
        fake.unique.clear()
    except Exception:
        pass
