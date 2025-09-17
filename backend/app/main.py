# backend/app/main.py
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .db import Base, engine, SessionLocal
from .seed import seed_if_needed
from .routers import customers, events

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # 2) Seed only after tables exist
    if os.getenv("SEED_ON_START", "false").lower() == "true":
        with SessionLocal() as db:
            seed_if_needed(db)

    yield  # shutdown code (if any) after this

app = FastAPI(lifespan=lifespan)

app.include_router(customers.router, prefix="/api")
app.include_router(events.router, prefix="/api")

@app.get("/")
def index():
    return {"ok": True}
