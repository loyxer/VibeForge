"""Counting visits to published sites."""
import json

import pytest
from fastapi.testclient import TestClient

from app import projects, publishing, usage, versions, visits
from app.api import routes
from app.generation.mock import MockGenerator
from app.main import app

CHROME = "Mozilla/5.0 (Macintosh) Chrome/140"


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


def published(client):
    done = [json.loads(line) for line in client.post("/api/generate", json={"prompt": "кав’ярня"}).text.splitlines()][-1]
    url = client.post(f"/api/projects/{done['project_id']}/publish").json()["published_url"]
    return done["project_id"], url.rsplit("/", 1)[1]


def visit(client, slug, ip="1.1.1.1", ua=CHROME):
    return client.post(f"/api/pages/{slug}/seen", headers={"X-Forwarded-For": ip, "User-Agent": ua})


def test_published_page_has_the_counter_once(client):
    _, slug = published(client)
    page = client.get(f"/s/{slug}").text
    assert f"/api/pages/{slug}/seen" in page and page.count('id="vf-visits"') == 1


def test_views_and_unique_visitors(client):
    project_id, slug = published(client)
    assert visit(client, slug).status_code == 200
    visit(client, slug)  # a reload right away counts once
    visit(client, slug, ip="2.2.2.2")
    visit(client, slug, ip="3.3.3.3", ua="TelegramBot (like TwitterBot)")  # link preview
    assert client.get(f"/api/projects/{project_id}/visits").json() == {
        "today": 2,
        "views_7d": 2,
        "visitors_7d": 2,
        "views_30d": 2,
        "total": 2,
    }


def test_no_ip_address_is_stored(client):
    _, slug = published(client)
    visit(client, slug, ip="9.8.7.6")
    stored = visits._STORE_PATH.read_text()
    assert "9.8.7.6" not in stored and CHROME not in stored


def test_unknown_page_and_someone_elses_site(client):
    project_id, _ = published(client)
    assert visit(client, "nosuchpg").status_code == 404
    assert client.get("/api/projects/nope/visits").status_code == 404


def test_visits_go_with_the_site(client):
    project_id, slug = published(client)
    visit(client, slug)
    client.delete(f"/api/projects/{project_id}")
    assert json.loads(visits._STORE_PATH.read_text()) == []
