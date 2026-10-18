"""Form submissions ("leads") from published sites, sent to the site's owner
in Telegram.

- Publishing adds a small script to the page (with_form_capture) that sends
  whatever a visitor submits in any form to POST /api/forms/<slug>.
- Each submission is stored (table `form_submissions`), so nothing is lost
  if Telegram is down or not connected yet, and forwarded by the VibeForge
  bot to the owner's chat, if they've connected one.
- Connecting: the app asks for a one-time link to the bot with a code;
  pressing Start in Telegram sends "/start <code>" to our webhook, which
  remembers that chat for that account (table `telegram_links`).

Making sites by writing to the bot lives in chat_sites.py.

Needs TELEGRAM_BOT_TOKEN (from @BotFather). Without it forms are still
stored, just not forwarded, and the app says Telegram isn't available.
"""
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app import projects, publishing, supabase
from app.supabase import rest as _rest

logger = logging.getLogger("vibeforge")

_LINK_VALID_FOR = timedelta(minutes=15)
MAX_FIELDS = 20
MAX_LABEL = 60
MAX_VALUE = 1000


class TooMany(RuntimeError):
    """Too many submissions from one visitor or to one site."""


# ------------------------------------------------------------- the bot


def bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def webhook_secret() -> str:
    """Telegram sends this back with every update, so only it can call our
    webhook. Derived from the token: nothing extra to configure."""
    return hashlib.sha256(f"vibeforge-webhook:{bot_token()}".encode()).hexdigest()[:48]


_username: dict[str, str] = {}


def bot_username() -> Optional[str]:
    token = bot_token()
    if not token:
        return None
    if token not in _username:
        res = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        res.raise_for_status()
        _username[token] = res.json()["result"]["username"]
    return _username[token]


def typing(chat_id: int) -> None:
    """Show "typing…" in the chat for a few seconds (Telegram clears it)."""
    token = bot_token()
    if not token:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=10,
        )
    except httpx.HTTPError:
        pass


def send(chat_id: int, text: str) -> bool:
    token = bot_token()
    if not token:
        return False
    try:
        res = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
    except httpx.HTTPError as e:
        logger.warning("Telegram send failed: %s", e)
        return False
    if res.status_code != 200:
        logger.warning("Telegram send -> %s %s", res.status_code, res.text[:200])
    return res.status_code == 200


def register_webhook() -> None:
    """Point the bot at this server. Only on Render, which knows its public
    URL — a laptop running the app must never steal the live webhook."""
    base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    token = bot_token()
    if not (base and token):
        return
    try:
        res = httpx.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": f"{base}/api/telegram/webhook",
                "secret_token": webhook_secret(),
                "allowed_updates": ["message"],
            },
            timeout=15,
        )
        logger.info("Telegram webhook: %s", res.json().get("description"))
    except httpx.HTTPError as e:
        logger.warning("Telegram webhook not set: %s", e)


# ---------------------------------------------------------- connecting


def status(owner: str) -> dict[str, Any]:
    if not bot_token():
        return {"available": False, "connected": False}
    return {"available": True, "connected": _chat_of(owner) is not None}


def link_url(owner: str) -> str:
    """A one-time t.me link that connects the owner's Telegram when opened."""
    username = bot_username()
    if not username:
        raise RuntimeError("Telegram isn't set up")
    code = secrets.token_urlsafe(18)  # Telegram allows A-Z a-z 0-9 _ - here
    _save_link(owner, {"code": code, "code_expires_at": _now() + _LINK_VALID_FOR})
    return f"https://t.me/{username}?start={code}"


def disconnect(owner: str) -> None:
    _save_link(
        owner,
        {"chat_id": None, "code": None, "code_expires_at": None, "active_project_id": None},
    )


def owners_of_chat(chat_id: int) -> list[str]:
    return _owners_with_chat(chat_id)


def active_project_of(owner: str) -> Optional[str]:
    """The site the person is working on in the chat (see chat_sites.py)."""
    row = _link_row(owner)
    return row.get("active_project_id") if row else None


def set_active_project(owner: str, project_id: Optional[str]) -> None:
    _save_link(owner, {"active_project_id": project_id})


def handle_update(update: dict[str, Any]) -> None:
    """A message to the bot (from Telegram's webhook)."""
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return
    if text.startswith("/start"):
        code = text.removeprefix("/start").strip()
        owner = _owner_with_code(code) if code else None
        if owner is None:
            send(chat_id, HELP_TEXT)
            return
        # One chat belongs to one account, or the bot wouldn't know whose
        # sites it is making: the latest connection wins.
        others = [o for o in _owners_with_chat(chat_id) if o != owner]
        for other in others:
            disconnect(other)
        _save_link(owner, {"chat_id": chat_id, "code": None, "code_expires_at": None})
        send(chat_id, CONNECTED_TEXT + (MOVED_TEXT if others else ""))
    elif text.startswith("/stop"):
        for owner in _owners_with_chat(chat_id):
            disconnect(owner)
        send(chat_id, STOPPED_TEXT)
    else:
        send(chat_id, HELP_TEXT)


CONNECTED_TEXT = (
    "✅ Готово! Тепер:\n"
    "• заявки з форм на твоїх опублікованих сайтах приходитимуть сюди;\n"
    "• ти можеш просто написати мені, який сайт потрібен, — я його створю. "
    "Наприклад: «Сайт для кав'ярні у Львові».\n"
    "Усі команди — /help. Відключити — /stop або кнопка «Відключити» в меню акаунта."
)
MOVED_TEXT = (
    "\n\nЦей чат був підключений до іншого акаунта VibeForge — тепер він підключений лише до цього."
)
STOPPED_TEXT = "Заявки більше не надходитимуть сюди. Підключити знову можна в меню акаунта VibeForge."
HELP_TEXT = (
    "Це бот VibeForge: він створює сайти за описом і надсилає заявки з форм на них.\n"
    "Щоб підключити його, відкрий меню акаунта на сайті VibeForge і натисни «Підключити Telegram»."
)


# ------------------------------------------------------------- leads


def capture_script(slug: str) -> str:
    """Sends every form submitted on the published page to us. It doesn't
    stop the page's own handling (the "Thank you!" message stays)."""
    base = (os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000").rstrip("/")
    url = json.dumps(f"{base}/api/forms/{slug}")
    return (
        '<script id="vf-forms">(function(){var url=' + url + ";"
        'document.addEventListener("submit",function(e){var f=e.target;'
        'if(!f||f.tagName!=="FORM")return;var out=[];'
        'var skip=["password","hidden","submit","button","file","reset","image"];'
        'f.querySelectorAll("input,select,textarea").forEach(function(el){'
        'var t=(el.type||"").toLowerCase();if(skip.indexOf(t)>=0)return;'
        'if((t==="checkbox"||t==="radio")&&!el.checked)return;'
        'var v=(el.value||"").trim();if(!v)return;if(t==="checkbox"&&v==="on")v="✓";var l="";'
        'if(el.id){var x=f.querySelector("label[for=\\""+el.id+"\\"]");if(x)l=x.innerText||x.textContent;}'
        'if(!l&&el.closest("label"))l=el.closest("label").innerText||el.closest("label").textContent;'
        'l=(l||el.getAttribute("aria-label")||el.placeholder||el.name||t).replace(/\\s+/g," ").trim();'
        'out.push([l.slice(0,60),v.slice(0,1000)]);});'
        "if(!out.length)return;"
        'try{fetch(url,{method:"POST",mode:"no-cors",keepalive:true,'
        'headers:{"Content-Type":"text/plain"},body:JSON.stringify({fields:out})});}catch(_){}'
        "},true);})();</script>"
    )


def with_form_capture(html: str, slug: str) -> str:
    import re

    html = re.sub(r'<script id="vf-forms">.*?</script>', "", html, flags=re.S)
    if "<form" not in html.lower():
        return html
    m = re.search(r"</body>", html, re.I)
    at = m.start() if m else len(html)
    return html[:at] + capture_script(slug) + html[at:]


def submit(slug: str, fields: Any, ip: str) -> None:
    """A visitor sent a form. KeyError if the page isn't published (any more)."""
    project_id, owner = publishing.site_for(slug)
    clean = _clean(fields)
    if not clean:
        return
    _rate_limit(slug, ip)
    project = projects.get_project(project_id, owner)
    site_name = project.get("name") or (project["history"][0] if project["history"] else slug)
    chat_id = _chat_of(owner)
    delivered = chat_id is not None and send(chat_id, _message(site_name, clean))
    _store(project_id, owner, clean, delivered)


def _clean(fields: Any) -> list[list[str]]:
    if not isinstance(fields, list):
        return []
    out = []
    for pair in fields[:MAX_FIELDS]:
        if (
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(x, str) for x in pair)
            and pair[1].strip()
        ):
            out.append([pair[0].strip()[:MAX_LABEL] or "—", pair[1].strip()[:MAX_VALUE]])
    return out


def _message(site_name: str, fields: list[list[str]]) -> str:
    title = site_name if len(site_name) <= 60 else site_name[:57] + "…"
    lines = [f"📩 Нова заявка з сайту «{title}»", ""]
    lines += [f"{label}: {value}" for label, value in fields]
    return "\n".join(lines)


# Per site and per visitor, so a bot spamming one form can't flood a chat.
_recent: dict[str, deque] = defaultdict(deque)
_recent_lock = threading.Lock()
_LIMITS = {"site": (30, 3600), "ip": (5, 600)}  # (how many, per seconds)


def _rate_limit(slug: str, ip: str) -> None:
    now = time.monotonic()
    with _recent_lock:
        for kind, key in (("site", slug), ("ip", f"{slug}|{ip}")):
            count, window = _LIMITS[kind]
            q = _recent[f"{kind}:{key}"]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= count:
                raise TooMany(kind)
        for kind, key in (("site", slug), ("ip", f"{slug}|{ip}")):
            _recent[f"{kind}:{key}"].append(now)


# ------------------------------------------------- Supabase or local files


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _chat_of(owner: str) -> Optional[int]:
    row = _link_row(owner)
    return row.get("chat_id") if row else None


def _owner_with_code(code: str) -> Optional[str]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/telegram_links",
                params={"code": f"eq.{code}", "select": "user_id,code_expires_at"},
            )
        res.raise_for_status()
        rows = res.json()
        if rows and datetime.fromisoformat(rows[0]["code_expires_at"]) > _now():
            return rows[0]["user_id"]
        return None
    for owner, row in _read_links().items():
        if row.get("code") == code and datetime.fromisoformat(row["code_expires_at"]) > _now():
            return owner
    return None


def _owners_with_chat(chat_id: int) -> list[str]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/telegram_links", params={"chat_id": f"eq.{chat_id}", "select": "user_id"}
            )
        res.raise_for_status()
        return [r["user_id"] for r in res.json()]
    return [o for o, r in _read_links().items() if r.get("chat_id") == chat_id]


def _link_row(owner: str) -> Optional[dict]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/telegram_links",
                params={"user_id": f"eq.{owner}", "select": "chat_id,active_project_id"},
            )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    return _read_links().get(owner)


def _save_link(owner: str, change: dict[str, Any]) -> None:
    change = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in change.items()}
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/telegram_links",
                json={"user_id": owner, **change},
                params={"on_conflict": "user_id"},
                headers={"Prefer": "resolution=merge-duplicates"},
            )
        res.raise_for_status()
        return
    with _lock:
        links = _read_links()
        links[owner] = {**links.get(owner, {}), **change}
        _write(_LINKS_PATH, links)


def _store(project_id: str, owner: str, fields: list[list[str]], delivered: bool) -> None:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/form_submissions",
                json={
                    "project_id": project_id,
                    "user_id": owner,
                    "fields": fields,
                    "delivered": delivered,
                },
            )
        res.raise_for_status()
        return
    with _lock:
        rows = _read(_LEADS_PATH, [])
        rows.append(
            {
                "project_id": project_id,
                "owner": owner,
                "fields": fields,
                "delivered": delivered,
                "created_at": _now().isoformat(),
            }
        )
        _write(_LEADS_PATH, rows)


def forget_project(project_id: str) -> None:
    """Drop a deleted site's submissions (Supabase does this by cascade)."""
    if supabase.config():
        return
    with _lock:
        _write(_LEADS_PATH, [r for r in _read(_LEADS_PATH, []) if r["project_id"] != project_id])


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LINKS_PATH = _DATA_DIR / "telegram.json"
_LEADS_PATH = _DATA_DIR / "leads.json"
_lock = threading.Lock()


def _read_links() -> dict[str, dict]:
    return _read(_LINKS_PATH, {})


def _read(path: Path, empty):
    return json.loads(path.read_text()) if path.exists() else empty


def _write(path: Path, data) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
