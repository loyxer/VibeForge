"""Support / idea messages from users."""
import pytest
from fastapi.testclient import TestClient

from app import feedback, leads, usage
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback, "_PATH", tmp_path / "feedback.json")
    monkeypatch.setattr(leads, "_LINKS_PATH", tmp_path / "telegram.json")
    feedback._recent.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_message_is_stored_and_sent_to_owner(client, monkeypatch):
    sent = []
    monkeypatch.setattr(leads, "_chat_of", lambda owner: 42)
    monkeypatch.setattr(leads, "send", lambda chat, text: sent.append((chat, text)) or True)
    res = client.post("/api/feedback", json={"kind": "idea", "message": " Додайте темну тему ", "email": "a@b.c"})
    assert res.status_code == 200
    assert len(sent) == 1 and "Додайте темну тему" in sent[0][1] and "a@b.c" in sent[0][1]
    assert "Додайте темну тему" in feedback._PATH.read_text()


def test_works_without_telegram(client):
    res = client.post("/api/feedback", json={"kind": "problem", "message": "Не працює"})
    assert res.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "idea", "message": "   "},
        {"kind": "spam", "message": "hi"},
        {"kind": "idea", "message": "x" * 2001},
    ],
)
def test_bad_messages_rejected(client, body):
    assert client.post("/api/feedback", json=body).status_code == 400


def test_rate_limited(client):
    for _ in range(5):
        assert client.post("/api/feedback", json={"kind": "idea", "message": "hi"}).status_code == 200
    assert client.post("/api/feedback", json={"kind": "idea", "message": "hi"}).status_code == 429
