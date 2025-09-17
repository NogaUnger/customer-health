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


## System Diagram

```mermaid
flowchart LR
    subgraph Browser
        UI["Dashboard (HTML/JS)"]
    end

    subgraph Backend["FastAPI (Uvicorn)"]
        R1["Router: /api/customers/"]
        R2["Router: /api/events/"]
        R3["Router: /api/health/*"]
        S["scoring.py - factor calculations & weighting"]
        Seed["seed.py - sample data generator"]
    end

    DB[(PostgreSQL 16)]

    %% Static page
    UI -- "GET /api/dashboard" --> Backend
    Backend --> UI

    %% API usage from dashboard
    UI -- "GET /api/customers, /api/customers/{id}/health" --> R1
    UI -- "GET /api/health/summary, /api/health/trend" --> R3
    UI -- "POST /api/customers/{id}/events" --> R2

    %% Data flow
    R2 -- "insert events" --> DB
    R1 -- "read customers" --> DB
    R3 -- "aggregate, summarize" --> DB
    R1 -- "compute per-customer" --> S
    R3 -- "compute trends/summary" --> S

    %% Scoring storage
    S -- "optionally update health_score" --> DB

    %% Startup
    Seed -- "create tables & seed when SEED_ON_START=true" --> DB
