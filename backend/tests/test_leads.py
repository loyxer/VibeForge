"""Form submissions from published sites, and the Telegram bot."""
import json

import pytest
from fastapi.testclient import TestClient

from app import leads, projects, publishing, usage, versions
from app.api import routes
from app.generation.mock import MockGenerator
from app.main import app

PAGE = (
    "<!doctype html><html><head><title>Крихта</title></head><body>"
    '<form><label for="n">Ім’я</label><input id="n"><input type="tel" placeholder="Телефон">'
    "<button>Надіслати</button></form></body></html>"
)


class FormPage(MockGenerator):
    async def stream(self, request):
        yield ("model", "mock")
        yield ("text", PAGE)


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(publishing, "_STORE_PATH", tmp_path / "published.json")
    monkeypatch.setattr(versions, "_STORE_PATH", tmp_path / "versions.json")
    monkeypatch.setattr(leads, "_LINKS_PATH", tmp_path / "telegram.json")
    monkeypatch.setattr(leads, "_LEADS_PATH", tmp_path / "leads.json")
    monkeypatch.setattr(routes, "_generator", FormPage(delay=0))
    leads._recent.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def bot(monkeypatch):
    """A Telegram bot that records what it would send."""
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setattr(leads, "bot_username", lambda: "vibeforge_test_bot")
    monkeypatch.setattr(leads, "send", lambda chat_id, text: sent.append((chat_id, text)) or True)
    return sent


def published(client):
    done = [json.loads(line) for line in client.post("/api/generate", json={"prompt": "кав’ярня Крихта"}).text.splitlines()][-1]
    url = client.post(f"/api/projects/{done['project_id']}/publish").json()["published_url"]
    return done["project_id"], url.rsplit("/", 1)[1]


def send_form(client, slug, fields, ip="1.2.3.4"):
    return client.post(
        f"/api/forms/{slug}",
        content=json.dumps({"fields": fields}),
        headers={"Content-Type": "text/plain", "X-Forwarded-For": ip},
    )


def test_published_page_sends_its_forms_to_us(client):
    _, slug = published(client)
    page = client.get(f"/s/{slug}").text
    assert f"/api/forms/{slug}" in page and 'id="vf-forms"' in page
    assert page.count('id="vf-forms"') == 1


def test_page_without_a_form_gets_no_script():
    assert "vf-forms" not in leads.with_form_capture("<html><body>hi</body></html>", "abcd1234")


def test_lead_goes_to_the_owners_telegram(client, bot):
    _, slug = published(client)
    code = client.post("/api/telegram/link").json()["url"].split("start=")[1]
    leads.handle_update({"message": {"chat": {"id": 777}, "text": f"/start {code}"}})
    assert client.get("/api/telegram").json() == {"available": True, "connected": True}

    assert send_form(client, slug, [["Ім’я", "Оля"], ["Телефон", "+380 67 000 00 00"]]).status_code == 200
    chat_id, text = bot[-1]
    assert chat_id == 777
    assert "Нова заявка з сайту «кав’ярня Крихта»" in text
    assert "Ім’я: Оля" in text and "Телефон: +380 67 000 00 00" in text
    assert json.loads(leads._LEADS_PATH.read_text())[-1]["delivered"] is True


def test_lead_is_kept_even_without_telegram(client):
    _, slug = published(client)
    assert send_form(client, slug, [["Ім’я", "Оля"]]).status_code == 200
    row = json.loads(leads._LEADS_PATH.read_text())[-1]
    assert row["fields"] == [["Ім’я", "Оля"]] and row["delivered"] is False


def test_bad_or_unknown(client):
    _, slug = published(client)
    assert send_form(client, "nosuchpg", [["a", "b"]]).status_code == 404
    assert client.post(f"/api/forms/{slug}", content="not json").status_code == 400
    assert send_form(client, slug, "nope").status_code == 200  # nothing usable: ignored
    assert not leads._LEADS_PATH.exists()


def test_flooding_is_stopped(client):
    _, slug = published(client)
    codes = [send_form(client, slug, [["a", "b"]]).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    assert send_form(client, slug, [["a", "b"]], ip="5.6.7.8").status_code == 200  # someone else


def test_unpublished_page_takes_no_more_forms(client):
    project_id, slug = published(client)
    client.delete(f"/api/projects/{project_id}/publish")
    assert send_form(client, slug, [["a", "b"]]).status_code == 404


def test_webhook_needs_the_secret(client, bot):
    update = {"message": {"chat": {"id": 1}, "text": "/start"}}
    assert client.post("/api/telegram/webhook", json=update).status_code == 403
    res = client.post(
        "/api/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": leads.webhook_secret()},
    )
    assert res.status_code == 200 and "Це бот VibeForge" in bot[-1][1]


def test_old_or_wrong_codes_dont_connect(client, bot, monkeypatch):
    client.post("/api/telegram/link")
    leads.handle_update({"message": {"chat": {"id": 5}, "text": "/start wrongcode"}})
    assert client.get("/api/telegram").json()["connected"] is False

    monkeypatch.setattr(leads, "_LINK_VALID_FOR", leads.timedelta(seconds=-1))
    code = client.post("/api/telegram/link").json()["url"].split("start=")[1]
    leads.handle_update({"message": {"chat": {"id": 5}, "text": f"/start {code}"}})
    assert client.get("/api/telegram").json()["connected"] is False


def test_stop_and_disconnect(client, bot):
    code = client.post("/api/telegram/link").json()["url"].split("start=")[1]
    leads.handle_update({"message": {"chat": {"id": 9}, "text": f"/start {code}"}})
    leads.handle_update({"message": {"chat": {"id": 9}, "text": "/stop"}})
    assert client.get("/api/telegram").json()["connected"] is False

    code = client.post("/api/telegram/link").json()["url"].split("start=")[1]
    leads.handle_update({"message": {"chat": {"id": 9}, "text": f"/start {code}"}})
    client.delete("/api/telegram")
    assert client.get("/api/telegram").json()["connected"] is False


def test_without_a_bot_token(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert client.get("/api/telegram").json() == {"available": False, "connected": False}
    assert client.post("/api/telegram/link").status_code == 503
