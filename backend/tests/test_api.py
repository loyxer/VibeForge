"""API behaviour in local mode (JSON store, mock generator)."""
import asyncio
import json
import time
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import projects, usage
from app.api import routes
from app.generation.mock import MockGenerator
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(routes, "_generator", MockGenerator(delay=0))


@pytest.fixture
def client():
    return TestClient(app)


def stream(client, prompt, project_id=None):
    """All events of one /api/generate stream (the HTTP status must be 200)."""
    res = client.post("/api/generate", json={"prompt": prompt, "project_id": project_id})
    assert res.status_code == 200, res.text
    return [json.loads(line) for line in res.text.splitlines()]


def generate(client, prompt, project_id=None):
    """The final event of a generation: "done" or "error"."""
    return stream(client, prompt, project_id)[-1]


def test_project_lifecycle(client):
    done = generate(client, "a coffee shop")
    assert done["type"] == "done"
    project_id = done["project_id"]

    assert generate(client, "make it blue", project_id)["project_id"] == project_id

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


def test_streams_the_site_in_pieces(client):
    events = stream(client, "a coffee shop")
    assert events[0] == {"type": "model", "text": "mock"}
    pieces = [e["text"] for e in events if e["type"] == "text"]
    assert len(pieces) > 1
    assert "".join(pieces).strip() == events[-1]["html"]


def test_reset_discards_the_half_written_site(client, monkeypatch):
    class DropsOut(MockGenerator):
        async def stream(self, request):
            yield ("model", "first")
            yield ("text", "<html>broken half")
            yield ("reset", "")
            yield ("model", "second")
            yield ("text", "<html>whole</html>")

    monkeypatch.setattr(routes, "_generator", DropsOut())
    monkeypatch.setattr(usage, "DAILY_LIMIT", 5)
    done = generate(client, "x")
    assert done["html"] == "<html>whole</html>"
    assert done["remaining_today"] == 4  # one generation, not two


def test_slow_database_does_not_block_other_requests(monkeypatch):
    # The generate endpoint is async; a blocking database call made straight
    # from it would freeze the whole server. Simulate a slow database.
    def slow_remaining(user):
        time.sleep(1)
        return 5

    monkeypatch.setattr(usage, "remaining_today", slow_remaining)

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

    first = generate(client, "a")
    assert first["remaining_today"] == 1
    assert generate(client, "b")["remaining_today"] == 0

    res = client.post("/api/generate", json={"prompt": "c"})
    assert res.status_code == 429
    assert "2 free generations" in res.json()["detail"]
    # Editing an existing site counts too.
    res = client.post("/api/generate", json={"prompt": "d", "project_id": first["project_id"]})
    assert res.status_code == 429


def test_limit_resets_at_midnight(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    generate(client, "a")
    assert client.post("/api/generate", json={"prompt": "b"}).status_code == 429

    # Jump to tomorrow: today's generation no longer counts.
    tomorrow = usage.start_of_today() + timedelta(days=1)
    monkeypatch.setattr(usage, "start_of_today", lambda: tomorrow)
    assert client.get("/api/usage").json()["remaining_today"] == 1


def test_failed_generation_is_not_counted(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)

    class Broken(MockGenerator):
        async def stream(self, request):
            yield ("text", "<html>half a si")
            raise RuntimeError("model exploded")

    monkeypatch.setattr(routes, "_generator", Broken())
    error = generate(client, "a")
    assert error == {"type": "error", "status": 500, "detail": "RuntimeError: model exploded"}
    assert client.get("/api/usage").json()["remaining_today"] == 1
    assert client.get("/api/projects").json()["items"] == []


def test_limit_is_per_user(monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    usage.record("alice", "mock")
    assert usage.remaining_today("alice") == 0
    assert usage.remaining_today("bob") == 1


def test_zero_means_unlimited(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 0)
    for prompt in "abc":
        assert generate(client, prompt)["type"] == "done"
    assert client.get("/api/usage").json() == {"limit": None, "remaining_today": None}
