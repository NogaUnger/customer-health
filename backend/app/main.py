"""
main.py
========
Application entrypoint for the Customer Health API.

Responsibilities:
- Create the FastAPI app instance.
- Ensure database tables exist.
- Register API routers (customers/events).
- Optionally seed the database with realistic sample data on startup.
- Serve a tiny static dashboard at /api/dashboard.

Environment variables:
- DATABASE_URL   : SQLAlchemy URL for the database
                   (in Docker: postgresql+psycopg://app:app@db:5432/app;
                    locally defaults to SQLite if not set, see db.py).
- SEED_ON_START  : "true" to seed sample data on startup (default "false").
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .db import Base, engine, SessionLocal
from .routers import customers, events
from .seed import seed_if_needed


# -----------------------------------------------------------------------------
# Create tables up-front
# -----------------------------------------------------------------------------
# For this assignment we keep it simple and call create_all() at import time so
# tests and local runs have the schema ready. In production, you'd typically use
# migrations (e.g., Alembic) instead of create_all().
Base.metadata.create_all(bind=engine)


# -----------------------------------------------------------------------------
# Lifespan: run once on startup/shutdown
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context.

    Startup:
      - Optionally seed the database with sample data (controlled by SEED_ON_START).

    Shutdown:
      - Nothing to clean up here; SQLAlchemy sessions are scoped per request.
    """
    seed_flag = os.getenv("SEED_ON_START", "false").lower() == "true"
    if seed_flag:
        # Use a short-lived session for seeding so it does not interfere with requests.
        with SessionLocal() as db:
            seed_if_needed(db)
    print("✅ Customer Health API started")
    print("➡  Docs:      http://localhost:8000/docs")
    print("➡  Dashboard: http://localhost:8000/api/dashboard")
    # Hand control back to FastAPI to serve requests.
    yield

    # (If you had background workers, metrics flush, etc., you'd put cleanup here.)


# -----------------------------------------------------------------------------
# App instance and router registration
# -----------------------------------------------------------------------------
app = FastAPI(title="Customer Health API", lifespan=lifespan)
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return """
    <h1>Customer Health API</h1>
    <ul>
      <li><a href="/docs">Swagger API docs</a></li>
      <li><a href="/api/dashboard">Simple dashboard</a></li>
    </ul>
    """

# Mount versioned API routers. They expose:
# - GET  /api/customers
# - GET  /api/customers/{id}/health
# - POST /api/customers/{id}/events
app.include_router(customers.router)
app.include_router(events.router)


# -----------------------------------------------------------------------------
# Simple static dashboard
# -----------------------------------------------------------------------------
@app.get("/api/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard() -> str:
    """
    Serve a tiny HTML dashboard (no build step) that lists customers and shows
    a per-customer health breakdown on click.

    Returns:
        The contents of app/static/dashboard.html as raw HTML.
    """
    # Lazily read the static file so any edits reflect on next request in dev.
    path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
