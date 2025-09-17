from fastapi.testclient import TestClient
from app.main import app


"""
tests that both the urls for FastAPI app’s landing page are correct
"""
client = TestClient(app)

def test_index_links_present():
    r = client.get("/")
    assert r.status_code == 200
    assert "/docs" in r.text and "/api/dashboard" in r.text
