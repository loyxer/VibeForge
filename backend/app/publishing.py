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
from app.generation.languages import primary_only
from app.supabase import rest as _rest

SLUG_PATTERN = re.compile(r"^[a-z0-9]{8}$")
_SLUG_ALPHABET = string.ascii_lowercase + string.digits

# Generated pages are written by an AI, so they're served in a sandbox:
# a unique origin that can't read the cookies or storage of anything else
# on the domain (above all the VibeForge app and its sign-in session).
# Links that open in a new tab leave the sandbox, so a site's Facebook or
# Google Maps link (or our own badge) opens as a normal page.
SANDBOX_CSP = "sandbox allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals"


def public_url(slug: str) -> str:
    base = os.getenv("PUBLIC_SITE_BASE")
    if not base:
        frontend = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
        base = f"{frontend}/s/" if frontend else "http://localhost:8000/s/"
    return base + slug


def app_link(project_id: str) -> str:
    """A link that opens the site itself in VibeForge (for the Telegram bot)."""
    origin = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
    return f"{origin}/?open={project_id}" if origin else "VibeForge"


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
        data[slug] = {
            **data.get(slug, {}),  # keeps the owner's choice about search engines
            "project_id": project_id,
            "owner": owner,
            "html": html,
            "published_at": now,
        }
        _write(data)
        return slug


def _finish_page(html: str, slug: str) -> str:
    """What a published page gets on top of the site itself."""
    from app import leads, visits  # they use this module, so import them late

    html = with_seo_basics(html, public_url(slug))
    html = with_link_preview(html, public_url(slug))
    html = with_badge(html)
    return visits.with_visit_counter(leads.with_form_capture(html, slug), slug)


# The little "Made with VibeForge" label in the corner of every published
# site. Free sites carry it; a paid plan would leave it out (there are no
# plans yet, so every site gets it).
_BADGE = re.compile(r'\s*<a id="vf-badge".*?</a>', re.S)
_BADGE_TEXT = {"uk": "Зроблено у VibeForge", "en": "Made with VibeForge"}
_BADGE_STYLE = (
    "position:fixed!important;right:12px!important;bottom:12px!important;z-index:2147483647!important;"
    "display:inline-flex!important;align-items:center!important;gap:6px!important;padding:6px 12px!important;"
    "margin:0!important;border-radius:999px!important;background:#fff!important;color:#222!important;"
    "border:2px solid #e5e5e5!important;box-shadow:0 2px 0 #e5e5e5!important;"
    "font:700 13px/1.2 system-ui,-apple-system,Segoe UI,sans-serif!important;text-decoration:none!important;"
    "opacity:1!important;visibility:visible!important;transform:none!important"
)


def with_badge(html: str) -> str:
    html = _BADGE.sub("", html)
    lang = re.search(r"<html\b[^>]*\slang=[\"']?(\w+)", html, re.I)
    if 'data-l="' in html:
        # A two-language page: the badge speaks whichever language is shown.
        text = "".join(f'<span data-l="{code}">{words}</span>' for code, words in _BADGE_TEXT.items())
    else:
        text = _BADGE_TEXT["uk" if lang and lang.group(1).lower() in ("uk", "ua") else "en"]
    frontend = os.getenv("FRONTEND_ORIGIN", "").rstrip("/") or "http://localhost:5173"
    badge = (
        f'<a id="vf-badge" href="{html_lib.escape(frontend)}/?utm_source=vf-badge" target="_blank" '
        f'rel="noopener" style="{_BADGE_STYLE}">'
        f'<span aria-hidden="true">🔥</span>{text}</a>'
        "<style>@media print{#vf-badge{display:none!important}}</style>"
    )
    m = re.search(r"</body>", html, re.I)
    at = m.start() if m else len(html)
    return html[:at] + badge + html[at:]


def with_seo_basics(html: str, url: str) -> str:
    """What a search engine wants to find: the language of the page, a
    title, a description and the page's own address. Only fills in what the
    AI left out (the canonical address is always ours)."""
    head_end = re.search(r"</head>", html, re.I)
    if not head_end:
        return html
    extra = ""
    if not re.search(r"<title[^>]*>\s*\S", html, re.I):
        title = _text_of(r"<h1[^>]*>(.*?)</h1>", html)
        if title:
            html = re.sub(r"<title[^>]*>\s*</title>", "", html, flags=re.I)
            extra += f"\n<title>{html_lib.escape(title)}</title>"
    if not _meta_description(html):
        description = _first_paragraph(html)
        if description:
            extra += f'\n<meta name="description" content="{html_lib.escape(description, quote=True)}">'
    html = re.sub(r'\s*<link\s[^>]*rel="canonical"[^>]*>', "", html, flags=re.I)
    extra += f'\n<link rel="canonical" href="{html_lib.escape(url, quote=True)}">'
    head_end = re.search(r"</head>", html, re.I)
    html = html[: head_end.start()] + extra + "\n" + html[head_end.start() :]
    return _with_lang(html)


def _with_lang(html: str) -> str:
    tag = re.search(r"<html\b[^>]*>", html, re.I)
    if not tag or re.search(r"\slang=", tag.group(0), re.I):
        return html
    text = re.sub(r"<(script|style)\b.*?</\1>|<[^>]+>", " ", html, flags=re.I | re.S)
    cyrillic = len(re.findall(r"[а-яіїєґ]", text, re.I))
    latin = len(re.findall(r"[a-z]", text, re.I))
    lang = "uk" if cyrillic > latin else "en"
    new = tag.group(0)[:-1] + f' lang="{lang}">'
    return html[: tag.start()] + new + html[tag.end() :]


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
    html = primary_only(html)  # a two-language page: one language only
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
    html = primary_only(html)
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


def set_indexable(project_id: str, owner: str, value: bool) -> bool:
    """Let search engines list the published page (or not). Returns False if
    the project isn't published."""
    slug = slug_for(project_id, owner)
    if slug is None:
        return False
    if config := supabase.config():
        with _rest(config) as client:
            res = client.patch(
                "/published_sites", params={"slug": f"eq.{slug}"}, json={"indexable": value}
            )
        res.raise_for_status()
        return True
    with _lock:
        data = _read()
        data[slug]["indexable"] = value
        _write(data)
    return True


def is_indexable(project_id: str, owner: str) -> bool:
    slug = slug_for(project_id, owner)
    if slug is None:
        return False
    return is_slug_indexable(slug)


def is_slug_indexable(slug: str) -> bool:
    if not SLUG_PATTERN.match(slug):
        return False
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get("/published_sites", params={"slug": f"eq.{slug}", "select": "indexable"})
        res.raise_for_status()
        rows = res.json()
        return bool(rows and rows[0].get("indexable"))
    with _lock:
        return bool(_read().get(slug, {}).get("indexable"))


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
