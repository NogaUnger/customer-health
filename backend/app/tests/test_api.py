import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SEED_ON_START"] = "false"

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app import models
from app.scoring import compute_health_breakdown

client = TestClient(app)

def setup_module(_):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # insert 1 customer
    with SessionLocal() as db:
        c = models.Customer(name="Acme", segment=models.Segment.smb)
        db.add(c); db.commit()

def test_list_customers_empty_events():
    r = client.get("/api/customers")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) == 1
    assert "health_score" in arr[0]

def test_create_event_and_health():
    # create one login event
    r = client.post("/api/customers/1/events", json={"type":"login"})
    assert r.status_code == 201
    # health breakdown
    r2 = client.get("/api/customers/1/health")
    assert r2.status_code == 200
    body = r2.json()
    assert "total" in body and "factors" in body
