"""API behaviour in local mode (JSON store, mock generator)."""
import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import projects
from app.api import routes
from app.generation.base import GenerationResult
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")


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
