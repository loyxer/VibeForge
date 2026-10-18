"""The owner's stats page."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import projects, publishing, stats, usage, versions
from app.api import routes
from app.auth import current_user
from app.generation.mock import MockGenerator
from app.main import app

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(publishing, "_STORE_PATH", tmp_path / "published.json")
    monkeypatch.setattr(versions, "_STORE_PATH", tmp_path / "versions.json")
    monkeypatch.setattr(routes, "_generator", MockGenerator(delay=0))


@pytest.fixture
def client():
    return TestClient(app)


def test_owner_sees_stats(client):
    client.post("/api/generate", json={"prompt": "a cafe"})
    data = client.get("/api/stats").json()
    assert data["sites"]["total"] == 1
    assert data["generations"]["total"] == 1
    assert data["models_7d"] == [{"model": "mock", "count": 1}]
    assert client.get("/api/usage").json()["owner"] is True


def test_others_dont(client, monkeypatch):
    app.dependency_overrides[current_user] = lambda: "someone-else"
    try:
        assert client.get("/api/stats").status_code == 403
        assert client.get("/api/usage").json()["owner"] is False
    finally:
        app.dependency_overrides.clear()


def test_summary_numbers(monkeypatch):
    monkeypatch.setattr(usage, "UNLIMITED", {"me"})
    day = timedelta(days=1)
    users = [
        {"id": "me", "email": "ivan@example.com", "created_at": NOW - 30 * day, "last_sign_in_at": NOW - day},
        {"id": "ann", "email": "ann@example.com", "created_at": NOW - 2 * day, "last_sign_in_at": None},
    ]
    gens = [
        {"user_id": "ann", "model": "flash-lite", "created_at": NOW - 2 * day},
        {"user_id": "ann", "model": "flash", "created_at": NOW - 1 * day},
        {"user_id": "me", "model": "flash-lite", "created_at": NOW - 10 * day},
        {"user_id": "me", "model": "flash-lite", "created_at": NOW - timedelta(minutes=1)},
    ]
    data = stats.summarize(
        users=users,
        generations=gens,
        sites=[{"user_id": "ann"}, {"user_id": "me"}, {"user_id": "me"}],
        published=[{"user_id": "me"}],
        photos=[{"user_id": "me"}],
        now=NOW,
        today=NOW - timedelta(hours=1),
    )
    assert data["users"] == {"total": 2, "new_7d": 1, "active_7d": 2}
    assert data["generations"] == {"today": 1, "last_7d": 3, "last_30d": 4, "total": 4}
    assert data["models_7d"][0] == {"model": "flash-lite", "count": 2}
    assert data["sites"] == {"total": 3, "published": 1}
    first, second = data["people"]
    assert first["email"] == "iv***@example.com" and first["owner"] and first["sites"] == 2
    assert second["email"] == "an***@example.com" and not second["owner"]


def test_mask_email():
    assert stats.mask_email("loyxers@gmail.com") == "lo***@gmail.com"
    assert stats.mask_email("local") == "local"
