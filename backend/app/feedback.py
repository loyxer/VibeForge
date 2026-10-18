"""Support requests and ideas from users, sent to the owner.

Every message is stored (table `feedback`, or data/feedback.json locally) so
nothing is lost, and forwarded to the owner's Telegram — every owner account
that has connected the bot (see leads.py).
"""
import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from app import leads, supabase, usage
from app.auth import LOCAL_USER
from app.supabase import rest as _rest

KINDS = {"idea": "💡 Ідея", "problem": "🐞 Проблема", "question": "❓ Питання"}
MAX_LENGTH = 2000
_LIMIT = (5, 3600)  # messages per user per seconds


class TooMany(Exception):
    pass


class Invalid(Exception):
    pass


def submit(user: str, email: str, kind: str, message: str) -> None:
    message = message.strip()
    if kind not in KINDS:
        raise Invalid("Unknown kind")
    if not message:
        raise Invalid("Message is empty")
    if len(message) > MAX_LENGTH:
        raise Invalid("Message is too long")
    email = email.strip()[:120]
    _rate_limit(user)
    _store(user, email, kind, message)
    text = f"{KINDS[kind]} · VibeForge\n{email or user}\n\n{message}"
    for owner in _owner_ids():
        if chat_id := leads._chat_of(owner):
            leads.send(chat_id, text)


def _owner_ids() -> list[str]:
    return [LOCAL_USER, *sorted(usage.UNLIMITED)] if not supabase.config() else sorted(usage.UNLIMITED)


_recent: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _rate_limit(user: str) -> None:
    count, window = _LIMIT
    now = time.monotonic()
    with _lock:
        q = _recent[user]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= count:
            raise TooMany()
        q.append(now)


def _store(user: str, email: str, kind: str, message: str) -> None:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/feedback",
                json={"user_id": user, "email": email, "kind": kind, "message": message},
            )
        res.raise_for_status()
        return
    with _lock:
        try:
            rows = json.loads(_PATH.read_text())
        except (OSError, ValueError):
            rows = []
        rows.append(
            {
                "user": user,
                "email": email,
                "kind": kind,
                "message": message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


_PATH = Path(__file__).resolve().parent.parent / "data" / "feedback.json"
