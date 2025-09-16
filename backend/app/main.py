import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from .db import Base, engine, SessionLocal
from .routers import customers, events
from .seed import seed_if_needed

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("SEED_ON_START", "false").lower() == "true":
        with SessionLocal() as db:
            seed_if_needed(db)
    yield  # (shutdown work would go after this if needed)

app = FastAPI(title="Customer Health API", lifespan=lifespan)
app.include_router(customers.router)
app.include_router(events.router)

@app.get("/api/dashboard", response_class=HTMLResponse)
def dashboard():
    path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
