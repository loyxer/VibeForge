"""Making and changing sites by writing to the Telegram bot.

A connected chat works like the app's chat: a message describing a site
makes it, the next messages change it, /new starts another. Nothing becomes
public until the person sends /publish.

handle_update() answers commands itself and returns a Job when a message
should start a generation; the webhook route runs it (it needs the
generator, and takes minutes — Telegram wants its answer long before that).
"""
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from app import leads, projects, publishing, usage

MAX_PROMPT = 4000
_MIN_PROMPT = 3


@dataclass
class Job:
    chat_id: int
    owner: str
    prompt: str
    project_id: Optional[str]  # None = a new site


_lock = threading.Lock()
_busy: set[int] = set()  # chats waiting for a site right now
_seen: deque = deque(maxlen=200)  # update ids, in case Telegram redelivers


def handle_update(update: dict[str, Any]) -> Optional[Job]:
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return None
    with _lock:
        update_id = update.get("update_id")
        if update_id is not None:
            if update_id in _seen:
                return None
            _seen.append(update_id)

    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if command in ("/start", "/stop"):
        leads.handle_update(update)
        return None

    owners = leads.owners_of_chat(chat_id)
    if not owners:
        leads.send(chat_id, NOT_CONNECTED_TEXT)
        return None
    owner = owners[0]

    if command == "/help":
        leads.send(chat_id, HELP_TEXT)
    elif command == "/new":
        leads.set_active_project(owner, None)
        leads.send(chat_id, NEW_TEXT)
    elif command == "/publish":
        _publish(chat_id, owner)
    elif command:
        leads.send(chat_id, HELP_TEXT)
    else:
        return _start(chat_id, owner, text)
    return None


def _start(chat_id: int, owner: str, text: str) -> Optional[Job]:
    if len(text) < _MIN_PROMPT:
        leads.send(chat_id, HELP_TEXT)
        return None
    if usage.remaining_today(owner) == 0:
        leads.send(chat_id, LIMIT_TEXT.format(limit=usage.limit_for(owner)))
        return None
    with _lock:
        if chat_id in _busy:
            leads.send(chat_id, BUSY_TEXT)
            return None
        _busy.add(chat_id)
    project_id = _active_site(owner)
    leads.send(chat_id, WORKING_EDIT_TEXT if project_id else WORKING_NEW_TEXT)
    return Job(chat_id, owner, text[:MAX_PROMPT], project_id)


def _active_site(owner: str) -> Optional[str]:
    project_id = leads.active_project_of(owner)
    if not project_id:
        return None
    try:
        projects.get_project(project_id, owner)
    except KeyError:  # deleted in the app since
        return None
    return project_id


def _publish(chat_id: int, owner: str) -> None:
    project_id = _active_site(owner)
    if not project_id:
        leads.send(chat_id, NO_SITE_TEXT)
        return
    slug = publishing.publish(project_id, owner)
    leads.send(chat_id, PUBLISHED_TEXT.format(url=publishing.public_url(slug)))


# --------------------------------------------------- after the generation


def finished(job: Job, project_id: str, remaining: Optional[int]) -> None:
    leads.set_active_project(job.owner, project_id)
    project = projects.get_project(project_id, job.owner)
    name = project.get("name") or job.prompt
    name = name if len(name) <= 40 else name[:37] + "…"
    text = DONE_TEXT.format(name=name, app=publishing.app_url())
    if remaining is not None:
        text += f"\nЗалишилось спроб сьогодні: {remaining} з {usage.limit_for(job.owner)}."
    leads.send(job.chat_id, text)
    release(job)


def failed(job: Job, status: int) -> None:
    leads.send(job.chat_id, FAILED_TEXTS.get(status, FAILED_TEXTS[500]))
    release(job)


def release(job: Job) -> None:
    with _lock:
        _busy.discard(job.chat_id)


NOT_CONNECTED_TEXT = (
    "Щоб створювати сайти тут, спершу підключи бота: відкрий меню акаунта на сайті VibeForge "
    "і натисни «Підключити Telegram»."
)
HELP_TEXT = (
    "Просто напиши, який сайт потрібен, — наприклад: «Сайт для кав'ярні у Львові». "
    "Наступні повідомлення змінюватимуть цей сайт («зроби шапку темнішою»).\n\n"
    "/publish — опублікувати сайт і отримати посилання\n"
    "/new — почати новий сайт\n"
    "/stop — відключити бота"
)
NEW_TEXT = "Добре, наступне повідомлення створить новий сайт. Попередній лишається в «Мої сайти»."
WORKING_NEW_TEXT = "⏳ Створюю сайт… це триває 1–3 хвилини."
WORKING_EDIT_TEXT = "⏳ Вношу зміни… це триває 1–3 хвилини."
BUSY_TEXT = "Я ще працюю над попереднім повідомленням, зачекай хвилину."
LIMIT_TEXT = "Ліміт на сьогодні вичерпано ({limit} на день). Завтра будуть нові спроби."
NO_SITE_TEXT = "Спершу створи сайт: просто напиши, який він має бути."
DONE_TEXT = (
    "✅ Готово: «{name}».\n\n"
    "Подивитись і поправити: {app} → «Мої сайти».\n"
    "Опублікувати й отримати посилання: /publish\n"
    "Змінити щось — просто напиши, що саме. Новий сайт — /new."
)
PUBLISHED_TEXT = (
    "🌐 Сайт опубліковано: {url}\n\n"
    "Його бачить кожен, хто має це посилання. Зняти з публікації можна в застосунку VibeForge. "
    "Після нових змін надішли /publish ще раз."
)
FAILED_TEXTS = {
    429: "Google AI зараз вичерпав загальний ліміт. Спробуй пізніше, гаразд?",
    503: "Моделі AI зараз перевантажені. Спробуй ще раз за кілька хвилин.",
    500: "Не вдалося створити сайт. Спробуй ще раз за хвилину.",
}
