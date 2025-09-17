from fastapi.testclient import TestClient
from app.main import app


"""
tests that both the urls for FastAPI app’s landing page are correct
"""
client = TestClient(app)


def test_api_docs_accessible():
    # Test that FastAPI's built-in docs are accessible
    r = client.get("/docs")
    assert r.status_code == 200


def test_dashboard_accessible():
    # Test that the dashboard is accessible
    r = client.get("/api/dashboard")
    assert r.status_code == 200
