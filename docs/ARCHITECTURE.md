# Architecture Overview

## Components
- FastAPI backend (Uvicorn) — serves REST API and static dashboard
- PostgreSQL 16 — persistent storage for customers + events
- Docker Compose — local orchestration

## Data Model
- Customer(id, name, segment, health_score, ...)
- Event(id, customer_id, type, feature_key?, value?, ts)

## Health Score Flow
- On demand: GET endpoints compute factors (logins, features, tickets, invoices, API trend), weight them, save total into Customer.health_score.
- Factors live in pp/scoring.py for clarity and tuning.

## Runtime & Config
- DATABASE_URL is provided by Compose.
- Seed data runs on startup when SEED_ON_START=true.
- Uvicorn serves on 0.0.0.0:8000; dashboard at /api/dashboard; docs at /docs.

## Testing
- pytest + pytest-cov run inside the backend container.
