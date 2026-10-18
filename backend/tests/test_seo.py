"""Search-engine basics for published pages, and the opt-in to be listed."""
import pytest
from fastapi.testclient import TestClient

from app import projects, publishing, usage, versions
from app.api import routes
from app.main import app
from app.publishing import with_seo_basics

URL = "https://vibe.example/s/abcd1234"


def test_fills_in_what_is_missing():
    html = with_seo_basics(
        "<!doctype html><html><head></head><body><h1>Кава на Ринку</h1>"
        "<p>" + "Смачна кава щодня зранку. " * 4 + "</p></body></html>",
        URL,
    )
    assert "<title>Кава на Ринку</title>" in html
    assert 'name="description"' in html
    assert f'<link rel="canonical" href="{URL}">' in html
    assert '<html lang="uk">' in html


def test_keeps_what_the_ai_wrote():
    html = with_seo_basics(
        '<html lang="en"><head><title>Mine</title><meta name="description" content="Own text">'
        '<link rel="canonical" href="https://wrong.example/"></head><body><h1>Other</h1></body></html>',
        URL,
    )
    assert html.count("<title") == 1 and "Mine" in html
    assert html.count('name="description"') == 1
    assert html.count('rel="canonical"') == 1 and "wrong.example" not in html
    assert '<html lang="en">' in html


def test_english_page_gets_en():
    assert '<html lang="en">' in with_seo_basics(
        "<html><head><title>Cafe</title></head><body>Fresh coffee every morning</body></html>", URL
    )


def test_republishing_does_not_pile_up_tags():
    once = with_seo_basics("<html><head></head><body><h1>Hi</h1></body></html>", URL)
    assert with_seo_basics(once, URL).count("canonical") == 1


def test_page_without_head_is_left_alone():
    assert with_seo_basics("<html>whole</html>", URL) == "<html>whole</html>"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(publishing, "_STORE_PATH", tmp_path / "published.json")
    monkeypatch.setattr(versions, "_STORE_PATH", tmp_path / "versions.json")
    return TestClient(app)


def _published(client):
    pid = client.post("/api/generate", json={"prompt": "кав'ярня"}).text.split('"project_id": "')[1].split('"')[0]
    url = client.post(f"/api/projects/{pid}/publish").json()["published_url"]
    return pid, url.rsplit("/", 1)[1]


def test_hidden_from_search_until_the_owner_allows_it(client):
    pid, slug = _published(client)
    assert client.get(f"/api/projects/{pid}/seo").json() == {"indexable": False}
    assert client.get(f"/s/{slug}").headers["x-robots-tag"] == "noindex"

    assert client.put(f"/api/projects/{pid}/seo", json={"indexable": True}).json() == {"indexable": True}
    assert "x-robots-tag" not in client.get(f"/s/{slug}").headers

    # Re-publishing keeps the choice; unpublishing + publishing again resets it.
    client.post(f"/api/projects/{pid}/publish")
    assert client.get(f"/api/projects/{pid}/seo").json() == {"indexable": True}
    client.delete(f"/api/projects/{pid}/publish")
    client.post(f"/api/projects/{pid}/publish")
    assert client.get(f"/api/projects/{pid}/seo").json() == {"indexable": False}


def test_cannot_allow_search_for_an_unpublished_site(client):
    pid = client.post("/api/generate", json={"prompt": "x"}).text.split('"project_id": "')[1].split('"')[0]
    assert client.put(f"/api/projects/{pid}/seo", json={"indexable": True}).status_code == 409
    assert client.get("/api/projects/nope/seo").status_code == 404
