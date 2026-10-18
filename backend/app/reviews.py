"""A link for a client to look at a site and comment on it.

The owner switches the link on for a project; the client opens it with no
account, sees the project's current version, clicks anything on the page
and writes what should change. Comments are stored (table `review_comments`,
or data/reviews.json locally), shown to the owner under the preview, and
forwarded to the owner's Telegram if they've connected the bot.

The link's token is the only key: whoever has it can read the page and add
comments (never edit or delete anything), so the owner can switch it off.
"""
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import leads, projects, supabase
from app.supabase import rest as _rest

MAX_COMMENT = 1000
MAX_AUTHOR = 60
MAX_PER_PROJECT = 300
_LIMITS = {"link": (60, 24 * 3600), "visitor": (12, 600)}  # comments per window


class Invalid(ValueError):
    pass


class TooMany(RuntimeError):
    pass


# ---------------------------------------------------------- the owner


def enable(project_id: str, owner: str) -> str:
    """Switch the link on (it stays the same if already on); returns the token."""
    projects.get_project(project_id, owner)  # KeyError unless it's theirs
    if token := token_of(project_id, owner):
        return token
    token = secrets.token_urlsafe(12)
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/reviews", json={"project_id": project_id, "user_id": owner, "token": token}
            )
        res.raise_for_status()
        return token
    with _lock:
        data = _read()
        data["links"][project_id] = {"token": token, "owner": owner}
        _write(data)
    return token


def disable(project_id: str, owner: str) -> None:
    projects.get_project(project_id, owner)
    if config := supabase.config():
        with _rest(config) as client:
            client.delete(
                "/reviews", params={"project_id": f"eq.{project_id}", "user_id": f"eq.{owner}"}
            ).raise_for_status()
        return
    with _lock:
        data = _read()
        data["links"].pop(project_id, None)
        _write(data)


def token_of(project_id: str, owner: str) -> Optional[str]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/reviews",
                params={"project_id": f"eq.{project_id}", "user_id": f"eq.{owner}", "select": "token"},
            )
        res.raise_for_status()
        rows = res.json()
        return rows[0]["token"] if rows else None
    with _lock:
        link = _read()["links"].get(project_id)
    return link["token"] if link and link["owner"] == owner else None


def comments(project_id: str, owner: str) -> list[dict[str, Any]]:
    """All comments on a project, oldest first. KeyError unless it's the owner's."""
    projects.get_project(project_id, owner)
    return _comments(project_id)


def set_resolved(project_id: str, owner: str, comment_id: int, resolved: bool) -> None:
    projects.get_project(project_id, owner)
    if config := supabase.config():
        with _rest(config) as client:
            res = client.patch(
                "/review_comments",
                params={"id": f"eq.{comment_id}", "project_id": f"eq.{project_id}"},
                json={"resolved": resolved},
                headers={"Prefer": "return=representation"},
            )
        res.raise_for_status()
        if not res.json():
            raise KeyError(comment_id)
        return
    with _lock:
        data = _read()
        row = next((c for c in data["comments"] if c["id"] == comment_id and c["project_id"] == project_id), None)
        if row is None:
            raise KeyError(comment_id)
        row["resolved"] = resolved
        _write(data)


def delete_comment(project_id: str, owner: str, comment_id: int) -> None:
    projects.get_project(project_id, owner)
    if config := supabase.config():
        with _rest(config) as client:
            client.delete(
                "/review_comments",
                params={"id": f"eq.{comment_id}", "project_id": f"eq.{project_id}"},
            ).raise_for_status()
        return
    with _lock:
        data = _read()
        data["comments"] = [
            c for c in data["comments"] if not (c["id"] == comment_id and c["project_id"] == project_id)
        ]
        _write(data)


def forget_project(project_id: str) -> None:
    """Drop a deleted site's link and comments (Supabase does it by cascade)."""
    if supabase.config():
        return
    with _lock:
        data = _read()
        data["links"].pop(project_id, None)
        data["comments"] = [c for c in data["comments"] if c["project_id"] != project_id]
        _write(data)


# --------------------------------------------------------- the client


def project_for(token: str) -> tuple[str, str]:
    """(project_id, owner) behind a link; KeyError if it's wrong or switched off."""
    if not token or len(token) > 40:
        raise KeyError(token)
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get("/reviews", params={"token": f"eq.{token}", "select": "project_id,user_id"})
        res.raise_for_status()
        rows = res.json()
        if not rows:
            raise KeyError(token)
        return rows[0]["project_id"], rows[0]["user_id"]
    with _lock:
        links = _read()["links"]
    for project_id, link in links.items():
        if link["token"] == token:
            return project_id, link["owner"]
    raise KeyError(token)


def view(token: str) -> dict[str, Any]:
    """What the client's page shows: the site as it is now, and the comments."""
    project_id, owner = project_for(token)
    project = projects.get_project(project_id, owner)
    return {
        "name": project.get("name") or _title(project["html"]),
        "html": project["html"],
        "comments": [_public(c) for c in _comments(project_id)],
    }


def add_comment(token: str, author: str, text: str, selector: str, label: str, visitor: str) -> dict[str, Any]:
    project_id, owner = project_for(token)
    text, author = text.strip(), author.strip()[:MAX_AUTHOR]
    if not text:
        raise Invalid("Comment is empty")
    if len(text) > MAX_COMMENT:
        raise Invalid("Comment is too long")
    selector, label = selector[:400], label.strip()[:80]
    _rate_limit(token, visitor)
    if len(_comments(project_id)) >= MAX_PER_PROJECT:
        raise TooMany("link")
    comment = _insert(project_id, owner, author, text, selector, label)
    project = projects.get_project(project_id, owner)
    name = project.get("name") or _title(project["html"])
    message = f"💬 Коментар до «{name}»\n{author or 'Клієнт'}"
    if label:
        message += f" · {label}"
    message += f"\n\n{text}"
    if chat_id := leads._chat_of(owner):
        leads.send(chat_id, message)
    return _public(comment)


def _public(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c[k] for k in ("id", "author", "text", "selector", "label", "resolved", "created_at")}


def _title(html: str) -> str:
    import re

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return " ".join(m.group(1).split())[:80] if m and m.group(1).strip() else "Site"


_recent: dict[str, deque] = defaultdict(deque)


def _rate_limit(token: str, visitor: str) -> None:
    now = time.monotonic()
    keys = (("link", token), ("visitor", f"{token}|{visitor}"))
    with _lock:
        for kind, key in keys:
            count, window = _LIMITS[kind]
            q = _recent[f"{kind}:{key}"]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= count:
                raise TooMany(kind)
        for kind, key in keys:
            _recent[f"{kind}:{key}"].append(now)


# ------------------------------------------------- Supabase or local files


def _comments(project_id: str) -> list[dict[str, Any]]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/review_comments",
                params={
                    "project_id": f"eq.{project_id}",
                    "select": "id,author,text,selector,label,resolved,created_at",
                    "order": "id.asc",
                },
            )
        res.raise_for_status()
        return res.json()
    with _lock:
        return [c for c in _read()["comments"] if c["project_id"] == project_id]


def _insert(project_id: str, owner: str, author: str, text: str, selector: str, label: str) -> dict[str, Any]:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/review_comments",
                json={
                    "project_id": project_id,
                    "user_id": owner,
                    "author": author,
                    "text": text,
                    "selector": selector,
                    "label": label,
                },
                headers={"Prefer": "return=representation"},
            )
        res.raise_for_status()
        return res.json()[0]
    with _lock:
        data = _read()
        row = {
            "id": max([c["id"] for c in data["comments"]], default=0) + 1,
            "project_id": project_id,
            "author": author,
            "text": text,
            "selector": selector,
            "label": label,
            "resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data["comments"].append(row)
        _write(data)
    return row


_PATH = Path(__file__).resolve().parent.parent / "data" / "reviews.json"
_lock = threading.RLock()


def _read() -> dict[str, Any]:
    try:
        data = json.loads(_PATH.read_text())
    except (OSError, ValueError):
        data = {}
    return {"links": data.get("links", {}), "comments": data.get("comments", [])}


def _write(data: dict[str, Any]) -> None:
    _PATH.parent.mkdir(exist_ok=True)
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1))
