from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.db import SessionLocal
from app.models import Customer, Segment

client = TestClient(app)

def _mk_customer():
    name = f"TestCo-{uuid4()}"
    with SessionLocal() as db:
        c = Customer(name=name, segment=Segment.smb)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id

def test_dashboard_ok():
    r = client.get('/api/dashboard')
    assert r.status_code == 200
    assert 'Customer Health' in r.text or '<html' in r.text.lower()

def test_feature_use_ok():
    cid = _mk_customer()
    r = client.post(f'/api/customers/{cid}/events', json={
        'type': 'feature_use',
        'feature_key': 'feature_7'
    })
    assert r.status_code == 201
    body = r.json()
    assert body['type'] == 'feature_use'
    assert body['feature_key'] == 'feature_7'
    assert body['value'] is None

def test_feature_use_value_forbidden():
    cid = _mk_customer()
    r = client.post(f'/api/customers/{cid}/events', json={
        'type': 'feature_use',
        'value': 123
    })
    assert r.status_code == 422

def test_api_call_requires_value():
    cid = _mk_customer()
    r = client.post(f'/api/customers/{cid}/events', json={
        'type': 'api_call'
    })
    assert r.status_code == 422

def test_api_call_forbids_feature_key():
    cid = _mk_customer()
    r = client.post(f'/api/customers/{cid}/events', json={
        'type': 'api_call',
        'value': 10,
        'feature_key': 'nope'
    })
    assert r.status_code == 422

def test_api_call_ok():
    cid = _mk_customer()
    r = client.post(f'/api/customers/{cid}/events', json={
        'type': 'api_call',
        'value': 250
    })
    assert r.status_code == 201
    body = r.json()
    assert body['type'] == 'api_call'
    assert body['value'] == 250
    assert body['feature_key'] is None
