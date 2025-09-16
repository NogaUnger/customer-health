# API Documentation

## GET /api/customers
Returns all customers with current health scores.

## GET /api/customers/{id}/health
Returns a breakdown of the health score factors (0–100) and the weighted total.

## POST /api/customers/{id}/events
Records a new event. Body fields:
- type: one of login | feature_use | api_call | support_ticket_opened | invoice_paid | invoice_late
- feature_key (optional, for feature_use)
- value (optional, for api_call)
- ts (optional ISO datetime)

## GET /api/dashboard
Simple HTML page listing customers and showing per-customer breakdown on click.

**Interactive docs:** http://localhost:8000/docs  
**OpenAPI schema:**  http://localhost:8000/openapi.json
