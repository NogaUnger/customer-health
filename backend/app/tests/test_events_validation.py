from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.db import SessionLocal
from app.models import Customer, Segment

"""
These are endpoint validation tests for POST /api/customers/{id}/events.
They boot a real FastAPI app with TestClient, create a fresh customer directly in the DB (_mk_customer()), 
then hit the API with different payloads to verify both happy paths and validation errors.
They codify the contract for the events API:

1. feature_use ⇒ needs feature_key, forbids value
2. api_call ⇒ needs value, forbids feature_key
3. login / support_ticket_opened / invoice_* ⇒ no extras
Thus, if the schema or router logic changes, these tests will catch regressions immediately.
"""
client = TestClient(app)


"""
inserts a random SMB customer and returns its id. 
Each test gets its own customer so cases don’t interfere.
"""
def _mk_customer():
    name = f"TestCo-{uuid4()}"
    with SessionLocal() as db:
        c = Customer(name=name, segment=Segment.smb)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id

"""
Sends a feature use event with a feature_key. Expects 201 and response JSON where:
type == "feature_use", feature_key == "feature_7", and value is None.
"""
def test_feature_use_ok():
    cid = _mk_customer()
    r = client.post(f"/api/customers/{cid}/events", json={
        "type": "feature_use",
        "feature_key": "feature_7"
    })
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "feature_use"
    assert body["feature_key"] == "feature_7"
    assert body["value"] is None

"""
Sends a feature use event with a value (not allowed). Expects 422 Unprocessable Entity.
"""
def test_feature_use_value_forbidden():
    cid = _mk_customer()
    r = client.post(f"/api/customers/{cid}/events", json={
        "type": "feature_use",
        "value": 123
    })
    assert r.status_code == 422

"""
Sends an api_call event without value (required). Expects 422.
"""
def test_api_call_requires_value():
    cid = _mk_customer()
    r = client.post(f"/api/customers/{cid}/events", json={ "type": "api_call" })
    assert r.status_code == 422


"""
Sends an api_call event with feature_key (forbidden). Expects 422.
"""
def test_api_call_forbids_feature_key():
    cid = _mk_customer()
    r = client.post(f"/api/customers/{cid}/events", json={
        "type": "api_call",
        "value": 10,
        "feature_key": "nope"
    })
    assert r.status_code == 422


"""
Valid api_call with value: 250. Expects 201 and response JSON with:

type == "api_call", value == 250, and feature_key is None.
"""
def test_api_call_ok():
    cid = _mk_customer()
    r = client.post(f"/api/customers/{cid}/events", json={
        "type": "api_call",
        "value": 250
    })
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "api_call"
    assert body["value"] == 250
    assert body["feature_key"] is None


"""
For login events, both feature_key and value are forbidden:

With feature_key → 422

With value → 422

With neither (valid) → 201
"""
def test_login_forbids_feature_and_value():
    cid = _mk_customer()
    # feature_key forbidden
    r1 = client.post(f"/api/customers/{cid}/events", json={
        "type": "login",
        "feature_key": "nope"
    })
    assert r1.status_code == 422
    # value forbidden
    r2 = client.post(f"/api/customers/{cid}/events", json={
        "type": "login",
        "value": 5
    })
    assert r2.status_code == 422
    # valid login
    r3 = client.post(f"/api/customers/{cid}/events", json={ "type": "login" })
    assert r3.status_code == 201


"""
For invoice_paid, both feature_key and value are forbidden:

With extras → 422

Minimal valid body → 201
"""
def test_invoice_forbids_extras_and_allows_paid():
    cid = _mk_customer()
    # extras forbidden
    bad = client.post(f"/api/customers/{cid}/events", json={
        "type": "invoice_paid",
        "feature_key": "nope",
        "value": 1
    })
    assert bad.status_code == 422
    # ok
    ok = client.post(f"/api/customers/{cid}/events", json={ "type": "invoice_paid" })
    assert ok.status_code == 201
