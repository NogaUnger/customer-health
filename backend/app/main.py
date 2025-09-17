# backend/app/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine, SessionLocal
from .seed import seed_if_needed
from .routers import customers, events, analytics  # <— include analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables first
    Base.metadata.create_all(bind=engine)

    # Optional seeding
    if os.getenv("SEED_ON_START", "false").lower() == "true":
        with SessionLocal() as db:
            seed_if_needed(db)
    yield

app = FastAPI(lifespan=lifespan)

# static + dashboard
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/api/dashboard", response_class=HTMLResponse)
def dashboard():
    return FileResponse("app/static/dashboard.html")

# API routers
app.include_router(customers.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")  # <— adds /api/health/* endpoints
