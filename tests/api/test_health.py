import pytest
from fastapi.testclient import TestClient

from app.api.routes import health
from app.core.exceptions import DatabaseNotReady
from app.main import app


client = TestClient(app)


def test_live_does_not_require_database(monkeypatch):
    def unexpected_check():
        pytest.fail("Liveness must not query the database")

    monkeypatch.setattr(health, "check_database", unexpected_check)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready(monkeypatch):
    monkeypatch.setattr(health, "check_database", lambda: "0.8.0")
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "database": "ok", "pgvector": "0.8.0"
    }


@pytest.mark.parametrize("reason", ["database_unavailable", "vector_extension_missing"])
def test_not_ready(monkeypatch, reason):
    def failed_check():
        raise DatabaseNotReady(reason)

    monkeypatch.setattr(health, "check_database", failed_check)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": reason}
