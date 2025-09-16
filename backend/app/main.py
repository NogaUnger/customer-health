from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from .db import SessionLocal
from .seed import seed_if_needed
from .routers import customers, events


# Lifespan handler replaces @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("SEED_ON_START", "false").lower() == "true":
        # seed once on startup (safe no-op if already seeded)
        with SessionLocal() as db:
            seed_if_needed(db)
    yield
    # (No shutdown work yet)


app = FastAPI(title="Customer Health API", lifespan=lifespan)

# Routers
app.include_router(customers.router)
app.include_router(events.router)


# Root page with quick links
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return HTMLResponse(
        """
        <html>
          <head><title>Customer Health</title></head>
          <body style="font-family: system-ui; padding: 24px">
            <h1>Customer Health</h1>
            <ul>
              <li><a href="/api/dashboard">Dashboard</a></li>
              <li><a href="/docs">Interactive API docs</a></li>
            </ul>
          </body>
        </html>
        """
    )


# Serve the static dashboard HTML
@app.get("/api/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))
