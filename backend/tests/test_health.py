"""Tests for the health endpoint.

These are the only tests that exist today because the application logic is not
implemented yet. docs/07_TEST_STRATEGY.md describes the full intended suite.
"""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_reports_ok_status_and_version():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["service"]


def test_unknown_api_route_returns_404():
    assert client.get("/api/does-not-exist").status_code == 404
