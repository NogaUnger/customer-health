"""
Unit tests for the health-score *component* functions in `app.scoring`.

Scope
-----
These tests exercise small, pure helpers without touching the database.
They verify directional correctness and boundaries for each factor:
- clamp()                           → caps to [0, 100]
- score_login_frequency()           → more logins (same seats) → higher score; normalized by seats
- score_feature_adoption()          → more *unique* features → higher score
- score_support_ticket_volume()     → same tickets, more seats → milder penalty → higher score
- score_invoice_timeliness()        → recent 'late' lowers score more than old 'late'
- score_api_usage_trend()           → recent > previous → >50; equal → ~50; recent < previous → <50

Assumptions
-----------
`app/scoring.py` exports the functions imported below. If names differ, adjust
the imports in this file (no DB setup required).

How to run
----------
docker compose run --rm backend pytest -q \
  --cov=app --cov-report=term-missing \
  --cov-config=.coveragerc --cov-fail-under=80
"""

from datetime import datetime, timedelta
from app.models import Segment
from app.scoring import (
    clamp,
    score_login_frequency,
    score_feature_adoption,
    score_support_ticket_volume,
    score_invoice_timeliness,
    score_api_usage_trend,
)


def test_clamp_bounds_and_passthrough():
    """Values below 0 clamp to 0; above 100 clamp to 100; in-range pass through."""
    assert clamp(-10) == 0
    assert clamp(150) == 100
    assert clamp(42.5) == 42.5


def test_login_frequency_more_logins_higher_score():
    """With same seats/segment, more 30d logins → higher login-frequency score."""
    a = score_login_frequency(total_logins_30d=5, seats=20, segment=Segment.smb)
    b = score_login_frequency(total_logins_30d=15, seats=20, segment=Segment.smb)
    assert b > a


def test_login_frequency_normalizes_by_seats():
    """Same total logins: small org scores higher than large (per-seat normalization)."""
    small = score_login_frequency(total_logins_30d=20, seats=20, segment=Segment.smb)
    big   = score_login_frequency(total_logins_30d=20, seats=200, segment=Segment.smb)
    assert small > big


def test_feature_adoption_counts_uniques_not_repeats():
    """More *unique* features used in 30d → higher adoption score (repeats don’t inflate)."""
    base = score_feature_adoption(unique_features_30d=1)
    more = score_feature_adoption(unique_features_30d=4)
    assert more > base


def test_support_ticket_penalty_scales_with_seats():
    """Same ticket count: larger org penalized less per 100 seats → higher factor score."""
    small = score_support_ticket_volume(tickets_30d=6, seats=10,   segment=Segment.startup)
    big   = score_support_ticket_volume(tickets_30d=6, seats=1000, segment=Segment.enterprise)
    assert big > small


def test_invoice_timeliness_recent_late_hurts_more():
    """Recency weighting: a very recent 'late' lowers score more than old 'late'."""
    now = datetime.utcnow()
    mostly_paid = [
        ("invoice_paid", now - timedelta(days=5)),
        ("invoice_paid", now - timedelta(days=35)),
        ("invoice_paid", now - timedelta(days=75)),
    ]
    late_recent = [
        ("invoice_paid", now - timedelta(days=60)),
        ("invoice_late", now - timedelta(days=3)),  # recent late should drag down
    ]
    s_paid = score_invoice_timeliness(mostly_paid)
    s_late = score_invoice_timeliness(late_recent)
    assert s_paid > s_late


def test_api_usage_trend_up_neutral_down():
    """Trend uses 50 as neutral: up >50, equal ~50, down <50 (with log-ratio mapping)."""
    assert score_api_usage_trend(recent_sum=300, prev_sum=100) > 50      # up
    assert 45 <= score_api_usage_trend(recent_sum=100, prev_sum=100) <= 55  # neutral
    assert score_api_usage_trend(recent_sum=50,  prev_sum=200) < 50      # down
