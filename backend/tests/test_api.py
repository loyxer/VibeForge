"""API behaviour in local mode (JSON store, mock generator)."""
import asyncio
import json
import time
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import projects, publishing, usage, versions
from app.api import routes
from app.generation.mock import MockGenerator
from app.main import app


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


def test_responses_carry_the_api_version(client):
    from app.main import API_VERSION

    assert client.get("/api/projects").headers["X-API-Version"] == API_VERSION
    frontend = (Path(__file__).parents[2] / "frontend/src/api.ts").read_text()
    assert f"const API_VERSION = '{API_VERSION}'" in frontend  # kept in sync


def test_style_reaches_the_generator(client, monkeypatch):
    from app.generation.styles import STYLES

    seen = []

    class Recording(MockGenerator):
        async def stream(self, request):
            seen.append(request.style)
            async for event in super().stream(request):
                yield event

    monkeypatch.setattr(routes, "_generator", Recording(delay=0))
    generate(client, "a bakery")  # no style: the AI decides
    res = client.post("/api/generate", json={"prompt": "a bakery", "style": "retro"})
    assert res.status_code == 200
    assert seen == [None, STYLES["retro"]]


def test_unknown_style_rejected(client):
    res = client.post("/api/generate", json={"prompt": "x", "style": "vaporwave"})
    assert res.status_code == 400


def test_style_ids_match_the_frontend():
    from app.generation.styles import STYLES

    picker = (Path(__file__).parents[2] / "frontend/src/components/StylePicker.tsx").read_text()
    for style_id in STYLES:
        assert f"id: '{style_id}'" in picker


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


def test_unlimited_accounts_have_no_limit(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    monkeypatch.setattr(usage, "UNLIMITED", {"local"})  # the user in local mode
    for prompt in "abc":
        assert generate(client, prompt)["type"] == "done"
    assert client.get("/api/usage").json() == {"limit": None, "remaining_today": None}
    assert usage.remaining_today("someone-else") == 1  # others keep the limit


def test_zero_means_unlimited(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 0)
    for prompt in "abc":
        assert generate(client, prompt)["type"] == "done"
    assert client.get("/api/usage").json() == {"limit": None, "remaining_today": None}


def test_publish_serves_the_site_publicly_in_a_sandbox(client):
    project_id = generate(client, "a bakery")["project_id"]
    assert client.get(f"/api/projects/{project_id}").json()["published_url"] is None

    url = client.post(f"/api/projects/{project_id}/publish").json()["published_url"]
    slug = url.rsplit("/", 1)[1]
    assert publishing.SLUG_PATTERN.match(slug)
    assert client.get(f"/api/projects/{project_id}").json()["published_url"] == url

    page = client.get(f"/s/{slug}")
    assert page.status_code == 200
    assert "a bakery" in page.text
    assert page.headers["Content-Security-Policy"].startswith("sandbox")


def test_republish_keeps_the_link_and_updates_the_page(client):
    project_id = generate(client, "a bakery")["project_id"]
    url = client.post(f"/api/projects/{project_id}/publish").json()["published_url"]
    generate(client, "now a flower shop", project_id)
    # Not re-published yet: the old version is still what people see.
    assert "a bakery" in client.get("/s/" + url.rsplit("/", 1)[1]).text

    assert client.post(f"/api/projects/{project_id}/publish").json()["published_url"] == url
    assert "now a flower shop" in client.get("/s/" + url.rsplit("/", 1)[1]).text


def test_unpublish_and_delete_take_the_page_down(client):
    project_id = generate(client, "a bakery")["project_id"]
    slug = client.post(f"/api/projects/{project_id}/publish").json()["published_url"].rsplit("/", 1)[1]
    client.delete(f"/api/projects/{project_id}/publish")
    assert client.get(f"/s/{slug}").status_code == 404

    slug = client.post(f"/api/projects/{project_id}/publish").json()["published_url"].rsplit("/", 1)[1]
    client.delete(f"/api/projects/{project_id}")
    assert client.get(f"/s/{slug}").status_code == 404


def test_cannot_publish_someone_elses_project(client):
    assert client.post("/api/projects/nope/publish").status_code == 404
    assert client.get("/s/not-a-real-slug").status_code == 404


def test_published_url_uses_the_frontend_origin(monkeypatch):
    monkeypatch.delenv("PUBLIC_SITE_BASE", raising=False)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://vibe.example")
    assert publishing.public_url("abcd1234") == "https://vibe.example/s/abcd1234"


def test_every_generation_is_a_version(client):
    project_id = generate(client, "a bakery")["project_id"]
    generate(client, "make it blue", project_id)
    items = client.get(f"/api/projects/{project_id}/versions").json()["items"]
    assert [(v["number"], v["prompt"]) for v in items] == [(2, "make it blue"), (1, "a bakery")]
    assert "html" not in items[0]  # the list stays light

    first = client.get(f"/api/projects/{project_id}/versions/{items[1]['id']}").json()
    assert first["number"] == 1 and "a bakery" in first["html"]


def test_restore_brings_back_an_old_version_as_the_newest(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 5)
    project_id = generate(client, "a bakery")["project_id"]
    generate(client, "make it blue", project_id)
    v1 = client.get(f"/api/projects/{project_id}/versions").json()["items"][-1]

    state = client.post(f"/api/projects/{project_id}/versions/{v1['id']}/restore").json()
    assert "a bakery" in state["html"]
    assert state["history"][-1] == "↩ Restored version 1"

    items = client.get(f"/api/projects/{project_id}/versions").json()["items"]
    assert [v["number"] for v in items] == [3, 2, 1]  # nothing was deleted
    assert client.get("/api/usage").json()["remaining_today"] == 3  # restore is free
    assert "a bakery" in client.get(f"/api/projects/{project_id}").json()["html"]


def test_old_sites_get_their_current_state_as_version_one(client):
    project_id = projects.create_project("local", "<html>old site</html>", "an old prompt")
    items = client.get(f"/api/projects/{project_id}/versions").json()["items"]
    assert [(v["number"], v["prompt"]) for v in items] == [(1, "an old prompt")]


def test_versions_of_unknown_projects_are_404(client):
    assert client.get("/api/projects/nope/versions").status_code == 404
    project_id = generate(client, "a bakery")["project_id"]
    assert client.get(f"/api/projects/{project_id}/versions/999").status_code == 404
    assert client.post(f"/api/projects/{project_id}/versions/999/restore").status_code == 404


def test_text_edit_saves_a_free_new_version(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 5)
    project_id = generate(client, "a bakery")["project_id"]
    edited = "<!doctype html><html><body><h1>Fresh bread daily</h1></body></html>"

    state = client.post(f"/api/projects/{project_id}/text-edit", json={"html": edited}).json()
    assert state["html"] == edited
    assert state["history"][-1] == "✎ Edited text by hand"
    assert client.get(f"/api/projects/{project_id}").json()["html"] == edited
    items = client.get(f"/api/projects/{project_id}/versions").json()["items"]
    assert [v["number"] for v in items] == [2, 1]
    assert client.get("/api/usage").json()["remaining_today"] == 4  # only the generation counted


def test_text_edit_rejects_junk_and_other_peoples_projects(client):
    project_id = generate(client, "a bakery")["project_id"]
    assert client.post(f"/api/projects/{project_id}/text-edit", json={"html": "no html"}).status_code == 400
    huge = "<p>" + "x" * 1_000_001
    assert client.post(f"/api/projects/{project_id}/text-edit", json={"html": huge}).status_code == 400
    assert client.post("/api/projects/nope/text-edit", json={"html": "<p>x</p>"}).status_code == 404


def test_rename_project(client):
    project_id = generate(client, "a coffee shop")["project_id"]

    res = client.patch(f"/api/projects/{project_id}", json={"name": "  Кава  "})
    assert res.json() == {"name": "Кава"}
    assert client.get(f"/api/projects/{project_id}").json()["name"] == "Кава"
    assert client.get("/api/projects").json()["items"][0]["name"] == "Кава"

    # Blank goes back to the default (first request).
    client.patch(f"/api/projects/{project_id}", json={"name": " "})
    assert client.get(f"/api/projects/{project_id}").json()["name"] is None

    assert client.patch(f"/api/projects/{project_id}", json={"name": "x" * 81}).status_code == 400
    assert client.patch("/api/projects/nope", json={"name": "a"}).status_code == 404


def test_delete_account_removes_everything(client):
    project_id = generate(client, "a coffee shop")["project_id"]
    assert client.delete("/api/account").json() == {"status": "deleted"}
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.get("/api/projects").json()["items"] == []
