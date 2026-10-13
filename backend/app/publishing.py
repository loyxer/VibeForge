"""Publishing a project as a public page at <PUBLIC_SITE_BASE><slug>.

One published page per project: publishing again replaces the HTML under
the same slug, so a shared link always shows the latest published
version. In production the page is served by a Vercel function
(frontend/api/site.ts) straight from Supabase; the /s/<slug> route in
routes.py serves the same thing for local development.

Same two backends as projects.py: the `published_sites` table in Supabase
(see backend/supabase/schema.sql) or a local JSON file.
"""
import json
import os
import re
import secrets
import string
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import projects, supabase
from app.supabase import rest as _rest

SLUG_PATTERN = re.compile(r"^[a-z0-9]{8}$")
_SLUG_ALPHABET = string.ascii_lowercase + string.digits

# Generated pages are written by an AI, so they're served in a sandbox:
# a unique origin that can't read the cookies or storage of anything else
# on the domain (above all the VibeForge app and its sign-in session).
SANDBOX_CSP = "sandbox allow-scripts allow-forms allow-popups allow-modals"


def public_url(slug: str) -> str:
    base = os.getenv("PUBLIC_SITE_BASE")
    if not base:
        frontend = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
        base = f"{frontend}/s/" if frontend else "http://localhost:8000/s/"
    return base + slug


def publish(project_id: str, owner: str) -> str:
    """Publish (or re-publish) the project's current HTML; returns the slug.
    Raises KeyError if the project doesn't exist or isn't the owner's."""
    html = projects.get_project(project_id, owner)["html"]
    now = datetime.now(timezone.utc).isoformat()
    if config := supabase.config():
        slug = _sb_slug(config, project_id, owner)
        with _rest(config) as client:
            if slug:
                res = client.patch(
                    "/published_sites",
                    params={"slug": f"eq.{slug}"},
                    json={"html": html, "published_at": now},
                )
            else:
                slug = _new_slug()
                res = client.post(
                    "/published_sites",
                    json={
                        "slug": slug,
                        "project_id": project_id,
                        "user_id": owner,
                        "html": html,
                        "published_at": now,
                    },
                )
        res.raise_for_status()
        return slug
    with _lock:
        data = _read()
        slug = next((s for s, p in data.items() if p["project_id"] == project_id), None)
        slug = slug or _new_slug()
        data[slug] = {"project_id": project_id, "owner": owner, "html": html, "published_at": now}
        _write(data)
        return slug


def unpublish(project_id: str, owner: str) -> None:
    projects.get_project(project_id, owner)  # KeyError unless it's theirs
    if config := supabase.config():
        with _rest(config) as client:
            res = client.delete(
                "/published_sites",
                params={"project_id": f"eq.{project_id}", "user_id": f"eq.{owner}"},
            )
        res.raise_for_status()
        return
    with _lock:
        data = _read()
        _write({s: p for s, p in data.items() if p["project_id"] != project_id})


def slug_for(project_id: str, owner: str) -> Optional[str]:
    """The project's slug if it's published, else None."""
    if config := supabase.config():
        return _sb_slug(config, project_id, owner)
    with _lock:
        return next(
            (s for s, p in _read().items() if p["project_id"] == project_id and p["owner"] == owner),
            None,
        )


def page(slug: str) -> Optional[str]:
    """The published HTML for a slug, for anyone; None if there's no such page."""
    if not SLUG_PATTERN.match(slug):
        return None
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get("/published_sites", params={"slug": f"eq.{slug}", "select": "html"})
        res.raise_for_status()
        rows = res.json()
        return rows[0]["html"] if rows else None
    with _lock:
        entry = _read().get(slug)
        return entry["html"] if entry else None


def forget_project(project_id: str) -> None:
    """Drop the page of a deleted project (Supabase does this by cascade)."""
    if supabase.config():
        return
    with _lock:
        data = _read()
        _write({s: p for s, p in data.items() if p["project_id"] != project_id})


def _new_slug() -> str:
    return "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(8))


def _sb_slug(config, project_id: str, owner: str) -> Optional[str]:
    with _rest(config) as client:
        res = client.get(
            "/published_sites",
            params={
                "project_id": f"eq.{projects._as_uuid(project_id)}",
                "user_id": f"eq.{owner}",
                "select": "slug",
            },
        )
    res.raise_for_status()
    rows = res.json()
    return rows[0]["slug"] if rows else None


# --------------------------------------------------------------- JSON file

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "published.json"
_lock = threading.Lock()


def _read() -> dict[str, Any]:
    if not _STORE_PATH.exists():
        return {}
    return json.loads(_STORE_PATH.read_text())


def _write(data: dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2))
