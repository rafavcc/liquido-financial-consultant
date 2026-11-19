from fastapi.testclient import TestClient

from app.main import create_app


def test_health(tmp_path):
    assert TestClient(create_app(tmp_path / "db.sqlite")).get("/api/health").json() == {"status": "ok"}
