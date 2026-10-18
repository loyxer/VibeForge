"""How many people open each published site — for its owner.

Publishing adds a one-line script to the page that tells us "someone opened
this page" (POST /api/pages/<slug>/seen — a plain name, so
ad blockers that cut anything called "visits" or "track" leave it alone). Pages are cached by Vercel, so the
server that serves them can't count; the visitor's browser can. Link
previews (Telegram, Viber) don't run scripts, so they don't count.

No IP address is stored. Each visit keeps only an anonymous code made from
the IP, the browser and the day, with a server-side secret mixed in: it
tells repeat visits apart for "unique visitors" that day, but can't be
turned back into an address and changes every day.
"""
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app import publishing, supabase, usage
from app.supabase import rest as _rest

_MIN_GAP = 30  # seconds: a reload or a double fire counts once


def counter_script(slug: str) -> str:
    base = (os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000").rstrip("/")
    url = json.dumps(f"{base}/api/pages/{slug}/seen")
    return (
        '<script id="vf-visits">try{fetch(' + url + ',{method:"POST",mode:"no-cors",'
        "keepalive:true})}catch(e){}</script>"
    )


def with_visit_counter(html: str, slug: str) -> str:
    import re

    html = re.sub(r'<script id="vf-visits">.*?</script>', "", html, flags=re.S)
    m = re.search(r"</body>", html, re.I)
    at = m.start() if m else len(html)
    return html[:at] + counter_script(slug) + html[at:]


# slug -> (project_id, owner, when looked up): a popular page shouldn't cost
# a database lookup per visit. An unpublished page may still be counted for
# a few minutes — harmless.
_sites: dict[str, tuple[str, str, float]] = {}
_last_seen: dict[str, float] = {}
_lock = threading.Lock()
_SITE_TTL = 600


def record(slug: str, ip: str, user_agent: str) -> None:
    """A visit to a published page. KeyError if there's no such page."""
    if any(word in user_agent.lower() for word in ("bot", "crawler", "spider", "preview")):
        return
    now = time.monotonic()
    with _lock:
        cached = _sites.get(slug)
    if cached and now - cached[2] < _SITE_TTL:
        project_id, owner = cached[0], cached[1]
    else:
        project_id, owner = publishing.site_for(slug)
        with _lock:
            _sites[slug] = (project_id, owner, now)

    visitor = _visitor_code(ip, user_agent)
    with _lock:
        key = f"{slug}|{visitor}"
        if now - _last_seen.get(key, -_MIN_GAP) < _MIN_GAP:
            return
        _last_seen[key] = now
        if len(_last_seen) > 50_000:  # forget old entries now and then
            _last_seen.clear()
    _store(project_id, owner, visitor)


def summary(project_id: str, owner: str) -> dict[str, int]:
    """Views and unique visitors: today (Kyiv), last 7 and 30 days, all time."""
    now = datetime.now(timezone.utc)
    today = usage.start_of_today()
    rows, total = _rows(project_id, owner, since=now - timedelta(days=30))

    def window(since: datetime) -> list[dict]:
        return [r for r in rows if r["created_at"] >= since]

    def unique(rs: list[dict]) -> int:
        return len({(r["visitor"], r["created_at"].date()) for r in rs})

    week = window(now - timedelta(days=7))
    return {
        "today": len(window(today)),
        "views_7d": len(week),
        "visitors_7d": unique(week),
        "views_30d": len(rows),
        "total": total,
    }


def _visitor_code(ip: str, user_agent: str) -> str:
    secret = os.getenv("SUPABASE_SECRET_KEY") or "local"
    day = datetime.now(timezone.utc).date().isoformat()
    return hashlib.sha256(f"{secret}|{day}|{ip}|{user_agent}".encode()).hexdigest()[:16]


# ------------------------------------------------- Supabase or local file


def _store(project_id: str, owner: str, visitor: str) -> None:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/site_visits",
                json={"project_id": project_id, "user_id": owner, "visitor": visitor},
            )
        res.raise_for_status()
        return
    with _file_lock:
        rows = _read()
        rows.append(
            {
                "project_id": project_id,
                "owner": owner,
                "visitor": visitor,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _write(rows)


def _rows(project_id: str, owner: str, since: datetime) -> tuple[list[dict[str, Any]], int]:
    """Visits since a moment, plus the all-time count."""
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/site_visits",
                params={
                    "project_id": f"eq.{project_id}",
                    "user_id": f"eq.{owner}",
                    "created_at": f"gte.{since.isoformat()}",
                    "select": "visitor,created_at",
                },
            )
            res.raise_for_status()
            rows = res.json()
            total = client.get(
                "/site_visits",
                params={
                    "project_id": f"eq.{project_id}",
                    "user_id": f"eq.{owner}",
                    "select": "id",
                },
                headers={"Prefer": "count=exact", "Range": "0-0"},
            )
            total.raise_for_status()
        count = int(total.headers["Content-Range"].split("/")[1])
        return [{**r, "created_at": datetime.fromisoformat(r["created_at"])} for r in rows], count
    with _file_lock:
        mine = [r for r in _read() if r["project_id"] == project_id and r["owner"] == owner]
    rows = [
        {**r, "created_at": datetime.fromisoformat(r["created_at"])}
        for r in mine
        if datetime.fromisoformat(r["created_at"]) >= since
    ]
    return rows, len(mine)


def forget_project(project_id: str) -> None:
    """Drop a deleted site's visits (Supabase does this by cascade)."""
    if supabase.config():
        return
    with _file_lock:
        _write([r for r in _read() if r["project_id"] != project_id])


_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "visits.json"
_file_lock = threading.Lock()


def _read() -> list[dict]:
    return json.loads(_STORE_PATH.read_text()) if _STORE_PATH.exists() else []


def _write(rows: list[dict]) -> None:
    _STORE_PATH.parent.mkdir(exist_ok=True)
    _STORE_PATH.write_text(json.dumps(rows, indent=2))
