"""A link for a client to look at a site and comment on it."""
import json

import pytest
from fastapi.testclient import TestClient

from app import leads, projects, publishing, reviews, usage, versions
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


def project(client):
    done = [json.loads(line) for line in client.post("/api/generate", json={"prompt": "кав’ярня"}).text.splitlines()][-1]
    return done["project_id"]


def token_of(state):
    return state["url"].rsplit("/", 1)[1]


def comment(client, token, text="Зміни фото", **extra):
    body = {"author": "Олена", "text": text, "selector": "body>h1", "label": "Заголовок", **extra}
    return client.post(f"/api/reviews/{token}/comments", json=body, headers={"X-Forwarded-For": "2.2.2.2"})


def test_no_link_until_switched_on(client):
    pid = project(client)
    state = client.get(f"/api/projects/{pid}/review").json()
    assert state == {"url": None, "comments": []}


def test_the_client_sees_the_site_and_can_comment(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    page = client.get(f"/api/reviews/{token}").json()
    assert "<html" in page["html"] and page["comments"] == []
    assert comment(client, token).status_code == 200
    assert client.get(f"/api/reviews/{token}").json()["comments"][0]["text"] == "Зміни фото"
    mine = client.get(f"/api/projects/{pid}/review").json()
    assert [c["author"] for c in mine["comments"]] == ["Олена"]


def test_enabling_twice_gives_the_same_link(client):
    pid = project(client)
    first = client.post(f"/api/projects/{pid}/review").json()["url"]
    assert client.post(f"/api/projects/{pid}/review").json()["url"] == first


def test_switching_off_kills_the_link_but_keeps_comments(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    comment(client, token)
    state = client.delete(f"/api/projects/{pid}/review").json()
    assert state["url"] is None and len(state["comments"]) == 1
    assert client.get(f"/api/reviews/{token}").status_code == 404
    assert comment(client, token).status_code == 404


def test_wrong_tokens_are_404(client):
    assert client.get("/api/reviews/nope").status_code == 404
    assert comment(client, "x" * 50).status_code == 404


def test_comment_must_have_text_and_not_be_huge(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    assert comment(client, token, text="   ").status_code == 400
    assert comment(client, token, text="x" * 1001).status_code == 400


def test_owner_can_resolve_and_delete(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    cid = comment(client, token).json()["id"]
    state = client.patch(f"/api/projects/{pid}/review/comments/{cid}", json={"resolved": True}).json()
    assert state["comments"][0]["resolved"] is True
    assert client.get(f"/api/reviews/{token}").json()["comments"][0]["resolved"] is True
    state = client.delete(f"/api/projects/{pid}/review/comments/{cid}").json()
    assert state["comments"] == []
    assert client.patch(f"/api/projects/{pid}/review/comments/999", json={"resolved": True}).status_code == 404


def test_a_visitor_cannot_flood_comments(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    codes = [comment(client, token, text=f"c{i}").status_code for i in range(14)]
    assert codes[:12] == [200] * 12 and codes[12] == 429


def test_the_owner_gets_it_in_telegram(client, monkeypatch):
    sent = []
    monkeypatch.setattr(leads, "_chat_of", lambda owner: 42)
    monkeypatch.setattr(leads, "send", lambda chat, text: sent.append((chat, text)) or True)
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    comment(client, token, text="Більший шрифт")
    assert sent and sent[0][0] == 42 and "Більший шрифт" in sent[0][1] and "Олена" in sent[0][1]


def test_deleting_the_project_drops_link_and_comments(client):
    pid = project(client)
    token = token_of(client.post(f"/api/projects/{pid}/review").json())
    comment(client, token)
    client.delete(f"/api/projects/{pid}")
    assert client.get(f"/api/reviews/{token}").status_code == 404
    assert reviews._comments(pid) == []
