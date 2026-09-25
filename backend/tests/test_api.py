"""API behaviour in local mode (JSON store, mock generator)."""
import asyncio
import time
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import projects, usage
from app.api import routes
from app.generation.base import GenerationResult
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")


@pytest.fixture
def client():
    return TestClient(app)


def test_project_lifecycle(client):
    res = client.post("/api/generate", json={"prompt": "a coffee shop"})
    assert res.status_code == 200
    project_id = res.json()["project_id"]

    res = client.post(
        "/api/generate", json={"prompt": "make it blue", "project_id": project_id}
    )
    assert res.json()["project_id"] == project_id

    assert client.get(f"/api/projects/{project_id}").json()["history"] == [
        "a coffee shop",
        "make it blue",
    ]
    assert [p["id"] for p in client.get("/api/projects").json()["items"]] == [project_id]

    assert client.delete(f"/api/projects/{project_id}").status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_empty_prompt_rejected(client):
    assert client.post("/api/generate", json={"prompt": "  "}).status_code == 400


def test_unknown_project_is_404(client):
    res = client.post("/api/generate", json={"prompt": "x", "project_id": "nope"})
    assert res.status_code == 404


def test_slow_generation_does_not_block_other_requests(monkeypatch):
    class SlowGenerator:
        def generate(self, request):
            time.sleep(1)
            return GenerationResult(html="<html></html>")

    monkeypatch.setattr(routes, "_generator", SlowGenerator())

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            # Timed from the start: if the slow request blocked the event
            # loop, even the sleep below would only return after it's done.
            start = time.monotonic()
            slow = asyncio.create_task(c.post("/api/generate", json={"prompt": "x"}))
            await asyncio.sleep(0.1)
            await c.get("/api/projects")
            fast_done = time.monotonic() - start
            await slow
            return fast_done

    assert asyncio.run(run()) < 0.8


def test_daily_limit(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 2)
    assert client.get("/api/usage").json() == {"limit": 2, "remaining_today": 2}

    first = client.post("/api/generate", json={"prompt": "a"}).json()
    assert first["remaining_today"] == 1
    assert client.post("/api/generate", json={"prompt": "b"}).json()["remaining_today"] == 0

    res = client.post("/api/generate", json={"prompt": "c"})
    assert res.status_code == 429
    assert "2 free generations" in res.json()["detail"]
    # Editing an existing site counts too.
    res = client.post("/api/generate", json={"prompt": "d", "project_id": first["project_id"]})
    assert res.status_code == 429


def test_limit_resets_at_midnight(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    client.post("/api/generate", json={"prompt": "a"})
    assert client.post("/api/generate", json={"prompt": "b"}).status_code == 429

    # Jump to tomorrow: today's generation no longer counts.
    tomorrow = usage.start_of_today() + timedelta(days=1)
    monkeypatch.setattr(usage, "start_of_today", lambda: tomorrow)
    assert client.get("/api/usage").json()["remaining_today"] == 1


def test_failed_generation_is_not_counted(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)

    class Broken:
        def generate(self, request):
            raise RuntimeError("model exploded")

    monkeypatch.setattr(routes, "_generator", Broken())
    assert client.post("/api/generate", json={"prompt": "a"}).status_code == 500
    assert client.get("/api/usage").json()["remaining_today"] == 1


def test_limit_is_per_user(monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    usage.record("alice", "mock")
    assert usage.remaining_today("alice") == 0
    assert usage.remaining_today("bob") == 1


def test_zero_means_unlimited(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 0)
    for prompt in "abc":
        assert client.post("/api/generate", json={"prompt": prompt}).status_code == 200
    assert client.get("/api/usage").json() == {"limit": None, "remaining_today": None}
