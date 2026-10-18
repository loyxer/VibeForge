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


# ---------------------------------------------------- sites from the chat


def connect(client, chat_id=777):
    code = client.post("/api/telegram/link").json()["url"].split("start=")[1]
    leads.handle_update({"message": {"chat": {"id": chat_id}, "text": f"/start {code}"}})


def say(client, text, chat_id=777, update_id=None):
    """Writes to the bot and waits until it has finished its work."""
    import time
    update = {"message": {"chat": {"id": chat_id}, "text": text}}
    if update_id is not None:
        update["update_id"] = update_id
    res = client.post(
        "/api/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": leads.webhook_secret()},
    )
    assert res.status_code == 200
    deadline = time.monotonic() + 10
    while routes._chat_tasks and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not routes._chat_tasks, "the bot never finished"


@pytest.fixture
def persistent():
    """One event loop for the whole test, so a site the bot is still making
    in the background isn't cut off when the webhook request ends."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def chat(persistent, bot, monkeypatch):
    from app import chat_sites

    monkeypatch.setattr(leads, "typing", lambda chat_id: None)
    chat_sites._busy.clear()
    chat_sites._seen.clear()
    connect(persistent)
    bot.clear()
    return bot


def test_stranger_is_told_to_connect(persistent, bot):
    say(persistent, "сайт для кав'ярні", chat_id=555)
    assert "Підключити Telegram" in bot[-1][1]
    assert not projects._STORE_PATH.exists()


def test_message_makes_a_site_and_further_ones_change_it(persistent, chat):
    say(persistent, "сайт для кав'ярні")
    assert chat[0][1].startswith("⏳ Створюю")
    assert chat[-1][1].startswith("✅ Готово")
    items = persistent.get("/api/projects").json()["items"]
    assert len(items) == 1

    say(persistent, "зроби шапку темнішою")
    assert chat[-2][1].startswith("⏳ Вношу зміни")
    assert len(persistent.get("/api/projects").json()["items"]) == 1  # the same site
    history = persistent.get(f"/api/projects/{items[0]['id']}").json()["history"]
    assert history == ["сайт для кав'ярні", "зроби шапку темнішою"]


def test_new_starts_another_site(persistent, chat):
    say(persistent, "сайт для кав'ярні")
    say(persistent, "/new")
    say(persistent, "сайт для перукарні")
    assert len(persistent.get("/api/projects").json()["items"]) == 2


def test_nothing_is_public_until_publish(persistent, chat):
    say(persistent, "сайт для кав'ярні")
    assert not publishing._STORE_PATH.exists()
    say(persistent, "/publish")
    assert "Сайт опубліковано: " in chat[-1][1]
    slug = chat[-1][1].split("/s/")[1].split()[0]
    assert persistent.get(f"/s/{slug}").status_code == 200


def test_publish_without_a_site(persistent, chat):
    say(persistent, "/publish")
    assert chat[-1][1].startswith("Спершу створи сайт")


def test_daily_limit_applies_in_the_chat(persistent, chat, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_LIMIT", 1)
    say(persistent, "сайт для кав'ярні")
    say(persistent, "ще один сайт")
    assert chat[-1][1].startswith("Ліміт на сьогодні вичерпано")


def test_one_site_at_a_time_and_redelivery_is_ignored(persistent, chat):
    from app import chat_sites

    chat_sites._busy.add(777)
    say(persistent, "сайт для кав'ярні")
    assert chat[-1][1].startswith("Я ще працюю")
    chat_sites._busy.clear()
    say(persistent, "сайт для кав'ярні", update_id=9)
    count = len(chat)
    say(persistent, "сайт для кав'ярні", update_id=9)  # Telegram sent it again
    assert len(chat) == count


def test_a_failed_site_is_reported_and_frees_the_chat(persistent, chat, monkeypatch):
    class Broken(MockGenerator):
        async def stream(self, request):
            raise RuntimeError("boom")
            yield

    monkeypatch.setattr(routes, "_generator", Broken(delay=0))
    say(persistent, "сайт для кав'ярні")
    assert chat[-1][1].startswith("Не вдалося")
    monkeypatch.setattr(routes, "_generator", FormPage(delay=0))
    say(persistent, "сайт для кав'ярні")
    assert chat[-1][1].startswith("✅ Готово")


def test_disconnecting_forgets_the_site(persistent, chat):
    say(persistent, "сайт для кав'ярні")
    persistent.delete("/api/telegram")
    connect(persistent)
    chat.clear()
    say(persistent, "сайт для перукарні")
    assert len(persistent.get("/api/projects").json()["items"]) == 2


def test_one_chat_belongs_to_one_account(client, bot):
    leads._save_link("old-account", {"chat_id": 777})
    connect(client)  # the local test user connects the same chat
    assert leads.owners_of_chat(777) == ["local"]
    assert "лише до цього" in bot[-1][1]


def test_done_message_links_to_the_site(persistent, chat, monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example")
    say(persistent, "сайт для кав'ярні")
    project_id = persistent.get("/api/projects").json()["items"][0]["id"]
    assert f"https://app.example/?open={project_id}" in chat[-1][1]
