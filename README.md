# Customer Health (FastAPI + Postgres)

A small, production-style sample that calculates **customer health scores** and exposes both a **REST API** and a **dashboard**. Comes with Docker one-command setup, database seeding, and automated tests with coverage.

---

## Stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic  
- **DB:** PostgreSQL 16  
- **Server:** Uvicorn (hot-reload in dev)  
- **Tests:** pytest + pytest-cov  
- **Packaging:** Docker + docker-compose

---

## Quickstart

> **Prereqs:** Docker Desktop (Win/Mac/Linux) with Compose v2 (`docker compose ...`)

```bash
# from the repo root (contains docker-compose.yml)
docker compose up --build

```
---
**Dashboard:** http://localhost:8000/api/dashboard

**OpenAPI docs:** http://localhost:8000/docs

**Postgres (local):** localhost:5432 (user: app, password: app, db: app)

Hot reload is enabled for the backend container. Edit files under backend/app/ and Uvicorn will reload automatically.

---

## Tests

Run all tests with coverage threshold (inside Docker):

docker compose run --rm backend \
  pytest -q --cov=app --cov-report=term-missing --cov-config=.coveragerc --cov-fail-under=80


What’s covered:

1. Unit tests for the scoring utilities

2. Integration tests for API routes (validation + responses)

3. Coverage report printed to the terminal
---

## Stop/Start

docker compose down          # stop

docker compose up -d         # start in background

---
## Reset the database (wipe all data)

docker compose down -v       # removes the 'dbdata' volume

docker compose up --build

---

## Project Layout
```
backend/

  Dockerfile
  
  app/
  
    main.py              # FastAPI app, lifespan, static mounting
    
    db.py                # engine, SessionLocal, Base
    
    models.py            # SQLAlchemy models (Customer, Event, etc.)
    
    schemas.py           # Pydantic request/response models
    
    scoring.py           # health scoring logic (weighted factors)
    
    seed.py              # synthetic data generator
    
    routers/
      
      customers.py       # list customers + per-customer health
      
      events.py          # validate + create events
      
      analytics.py       # /api/health/summary, /api/health/trend
   
    static/
      
      dashboard.html     # single-file dashboard (HTML+JS)

docker-compose.yml
```
