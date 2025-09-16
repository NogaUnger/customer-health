import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .db import Base, engine, SessionLocal
from . import models
from .routers import customers, events
from .seed import seed_if_needed

app = FastAPI(title="Customer Health API")

Base.metadata.create_all(bind=engine)

app.include_router(customers.router)
app.include_router(events.router)

@app.on_event("startup")
def startup():
    if os.getenv("SEED_ON_START", "false").lower() == "true":
        with SessionLocal() as db:
            seed_if_needed(db)

@app.get("/api/dashboard", response_class=HTMLResponse)
def dashboard():
    # super simple static dashboard (no build step)
    path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
