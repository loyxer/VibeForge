"""Publishing a project as a public page at <PUBLIC_SITE_BASE><slug>.

One published page per project: publishing again replaces the HTML under
the same slug, so a shared link always shows the latest published
version. In production the page is served by a Vercel function
(frontend/api/site.ts) straight from Supabase; the /s/<slug> route in
routes.py serves the same thing for local development.

Same two backends as projects.py: the `published_sites` table in Supabase
(see backend/supabase/schema.sql) or a local JSON file.
"""
import html as html_lib
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
        existing = _sb_slug(config, project_id, owner)
        slug = existing or _new_slug()
        html = _finish_page(html, slug)
        with _rest(config) as client:
            if existing:
                res = client.patch(
                    "/published_sites",
                    params={"slug": f"eq.{slug}"},
                    json={"html": html, "published_at": now},
                )
            else:
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
        html = _finish_page(html, slug)
        data[slug] = {"project_id": project_id, "owner": owner, "html": html, "published_at": now}
        _write(data)
        return slug


def _finish_page(html: str, slug: str) -> str:
    """What a published page gets on top of the site itself."""
    from app import leads  # leads uses this module, so import it late

    return leads.with_form_capture(with_link_preview(html, public_url(slug)), slug)


# What Telegram, Viber, Facebook and the rest show for a shared link: they
# read these tags from the page. The AI sometimes writes its own with
# made-up image paths, so ours replace them.
_PREVIEW_TAG = re.compile(r'\s*<meta\s[^>]*(?:property|name)="(?:og:|twitter:)[^"]*"[^>]*>', re.I)


def with_link_preview(html: str, url: str) -> str:
    head_end = re.search(r"</head>", html, re.I)
    if not head_end:
        return html
    html = _PREVIEW_TAG.sub("", html)
    title = _text_of(r"<title[^>]*>(.*?)</title>", html) or _text_of(r"<h1[^>]*>(.*?)</h1>", html)
    description = _meta_description(html) or _first_paragraph(html)
    image = _first_photo(html)
    tags = [
        ("og:type", "website"),
        ("og:url", url),
        ("og:title", title),
        ("og:description", description),
        ("og:image", image),
        ("twitter:card", "summary_large_image" if image else "summary"),
    ]
    block = "".join(
        f'\n<meta {"name" if key.startswith("twitter") else "property"}="{key}" '
        f'content="{html_lib.escape(value, quote=True)}">'
        for key, value in tags
        if value
    )
    head_end = re.search(r"</head>", html, re.I)
    return html[: head_end.start()] + block + "\n" + html[head_end.start() :]


def _text_of(pattern: str, html: str) -> str:
    m = re.search(pattern, html, re.I | re.S)
    return _plain(m.group(1)) if m else ""


def _plain(fragment: str, limit: int = 200) -> str:
    text = " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _meta_description(html: str) -> str:
    m = re.search(r'<meta\s[^>]*name="description"[^>]*>', html, re.I)
    content = re.search(r'content="([^"]*)"', m.group(0)) if m else None
    return _plain(content.group(1)) if content else ""


def _first_paragraph(html: str) -> str:
    body = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.I | re.S)
    for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", body, re.I | re.S):
        text = _plain(m.group(1))
        if len(text) >= 40:
            return text
    return ""


def _first_photo(html: str) -> str:
    """The first real photo on the page (ours or Unsplash's), as a full URL."""
    m = re.search(
        r'<img\b[^>]*\ssrc="(https://[^"]+)"|background-image:\s*url\([\'"]?(https://[^\'")]+)',
        html,
        re.I,
    )
    return html_lib.unescape(m.group(1) or m.group(2)) if m else ""


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


def site_for(slug: str) -> tuple[str, str]:
    """(project_id, owner) of a published page; KeyError if there's none."""
    if not SLUG_PATTERN.match(slug):
        raise KeyError(slug)
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/published_sites", params={"slug": f"eq.{slug}", "select": "project_id,user_id"}
            )
        res.raise_for_status()
        rows = res.json()
        if not rows:
            raise KeyError(slug)
        return rows[0]["project_id"], rows[0]["user_id"]
    with _lock:
        entry = _read().get(slug)
    if entry is None:
        raise KeyError(slug)
    return entry["project_id"], entry["owner"]


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
