# Health Score Methodology

We compute a 0–100 score from weighted sub-scores:
- Login frequency (last 30d)
- Feature adoption (distinct features last 30d)
- Support ticket volume (last 30d)
- Invoice timeliness (90d: paid vs late)
- API usage trend (last 7d vs previous 7d)

Weights:
- login_frequency: 0.25
- feature_adoption: 0.25
- support_ticket_volume: 0.20
- invoice_timeliness: 0.15
- api_usage_trend: 0.15

Interpretation:
- 80–100: Healthy
- 40–79: Watchlist
- 0–39: At risk

Assumptions & tuning notes:
- Thresholds chosen to be explainable and stable on small datasets.
- You can tune weights per segment in the future if needed.
