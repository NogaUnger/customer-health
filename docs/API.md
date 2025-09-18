# API Documentation

## Customers

### `GET /api/customers`
Returns a **paginated list of customers** with their current health scores.  

**Query parameters (optional):**
- `q` — search by name (case-insensitive substring).
- `segment` — filter by `startup | smb | enterprise`.
- `risk` — filter by `healthy | watch | at_risk`.
- `min_score`, `max_score` — numeric filters (0–100).
- `sort` — `health_score | name | id`.
- `order` — `asc | desc` (default `asc`).
- `limit` — page size (default 50).
- `offset` — skip count for pagination.

---

### `GET /api/customers/{id}/health`
Returns a **factor breakdown** of the health score (0–100 per factor) and the weighted total.  

**Example response:**
```json
{
  "total": 82.3,
  "factors": {
    "login_frequency": 90,
    "feature_adoption": 100,
    "support_ticket_volume": 70,
    "invoice_timeliness": 80,
    "api_usage_trend": 75
  }
}
```
---

### `POST /api/customers/{id}/events`
Records a **new event** for a customer 

**Request body** 
```json
{
  "type": "feature_use",
  "feature_key": "feature_7",
  "value": null,
  "ts": "2025-09-17T09:15:00Z"
}
```

**Allowed fields per type**
```
Allowed fields per type:
login → no feature_key, no value.
Example:
{
  "type": "login"
}
feature_use → requires feature_key, forbids value.
Example:
{
  "type": "feature_use", 
  "feature_key": "dashboard_view"
}
api_call → requires numeric value, forbids feature_key.
Example:
{
  "type": "api_call",
  "value": 150
}
support_ticket_opened → no extras.
invoice_paid → no extras.
invoice_late → no extras.

```
**Response:** Returns the created event with ID and timestamp. 

---

## Analytics

### `GET /api/health/summary`
Returns aggregated metrics across all customers (or filtered by segment).

Includes:
```
total customers
average score
risk distribution (healthy / watch / at risk)
average factor values
top 5 / bottom 5 customers by score
```
Used by the dashboard

---
### `GET /api/health/trend?days=30`

Returns a daily time series (last N days, default 30) of customer health distribution:

```
average score
25th percentile (p25)
75th percentile (p75)
```
Used by the dashboard for the trend chart.

---
### `Dashboard`
GET /api/dashboard

Serves the interactive HTML dashboard with charts, filters, and per-customer breakdowns.
