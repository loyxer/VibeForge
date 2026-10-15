"""Real, on-topic photos from Unsplash for generated sites.

The AI doesn't know any photo URLs, so it marks where a photo goes with a
short English description instead:

    <img data-photo="latte art on a wooden table" alt="...">
    <section class="hero" data-photo-bg="old town street at dusk">

After the site is written, fill() searches Unsplash for each description,
puts the photo in (src= for <img>, an inline background-image for
data-photo-bg), and adds the photo credits Unsplash requires at the bottom
of the page. Already-filled photos are left alone, so editing a site keeps
its photos.

Unsplash rules we follow (https://help.unsplash.com/en/articles/2511245):
hotlink their image URLs, credit photographer + Unsplash with links, and
tell Unsplash when a photo is actually used (its download_location).

Without UNSPLASH_ACCESS_KEY, or when the hourly limit is nearly used up,
photos are simply left out — the page still works, just without them.
"""
import html as html_lib
import logging
import os
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger("vibeforge")

_API = "https://api.unsplash.com"
_UTM = "utm_source=vibeforge&utm_medium=referral"
# Own colours: the page around this block can be dark, so nothing is inherited.
_LINK = "color:#111;text-decoration:underline"
MAX_PHOTOS_PER_PAGE = 8  # keeps one site within the 50-requests/hour demo limit
_CACHE_SECONDS = 24 * 60 * 60

# An opening tag carrying data-photo="…" or data-photo-bg="…".
_TAG = re.compile(r'<[a-zA-Z][^<>]*\bdata-photo(-bg)?="([^"]*)"[^<>]*>')
_CREDITS = re.compile(r'\s*<div class="vf-photo-credits".*?</div>', re.S)

# query -> (time fetched, list of photos)
_cache: dict[str, tuple[float, list[dict]]] = {}
# The last X-Ratelimit-Remaining Unsplash reported, and when. The limit is
# per hour, so an old reading says nothing about now.
_remaining = {"requests": 50, "at": 0.0}


def fill(html: str) -> str:
    """Put real photos into every unfilled data-photo / data-photo-bg tag."""
    key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    used: dict[str, int] = {}  # query -> how many times used on this page
    filled = 0

    def replace(match: re.Match) -> str:
        nonlocal filled
        tag, is_bg, query = match.group(0), bool(match.group(1)), match.group(2).strip()
        if _already_filled(tag, is_bg) or not query:
            return tag
        photo = None
        if key and filled < MAX_PHOTOS_PER_PAGE:
            photo = _pick(key, query, used.get(query, 0), "landscape" if is_bg else None)
        if photo is None:
            # No photo found: hide an <img> rather than show an empty frame
            # with its alt text; a background just keeps the page's colors.
            return tag if is_bg else _hidden(tag)
        used[query] = used.get(query, 0) + 1
        filled += 1
        _track_use(key, photo)
        # The first photo is usually the big one at the top: load it right
        # away; the rest can wait until they're scrolled near.
        return _with_photo(tag, is_bg, photo, lazy=filled > 1)

    html = _TAG.sub(replace, html)
    html = _hide_empty_frames(html)
    return _with_credits(html)


def _already_filled(tag: str, is_bg: bool) -> bool:
    if is_bg:
        return "background-image" in tag
    return re.search(r'\ssrc="[^"]+"', tag) is not None or re.search(r"\shidden\b", tag) is not None


def _hidden(tag: str) -> str:
    closing = "/>" if tag.endswith("/>") else ">"
    return tag[: -len(closing)].rstrip() + " hidden" + closing


# A hidden <img> that is the first thing inside a wrapper element.
_HIDDEN_IMG_IN_WRAPPER = re.compile(
    r"(<(div|figure|li|a|article)\b[^<>]*>)\s*<img\b[^<>]*\shidden\b[^<>]*>", re.I
)
# Things a plain photo frame doesn't contain; if they're inside, the wrapper
# is a real part of the page (a hero, an about section) and stays.
_NOT_A_FRAME = re.compile(r"<(section|form|input|textarea|button|video|iframe|h1|nav|header|footer)\b", re.I)
_MAX_CAPTION_CHARS = 120


def _hide_empty_frames(html: str) -> str:
    """Hide the tile around a photo that wasn't found, caption and all, so
    the gallery doesn't show a dark empty box. Only wrappers that hold
    nothing but that one photo and a short caption are hidden: the CSS of
    the site would otherwise keep the empty box, and hiding anything bigger
    could take real content with it."""
    edits = []
    for m in _HIDDEN_IMG_IN_WRAPPER.finditer(html):
        open_tag, name = m.group(1), m.group(2).lower()
        if re.search(r"\shidden\b", open_tag):
            continue  # already hidden on an earlier pass
        inner_start = m.end(1)
        inner_end = _closing_index(html, name, inner_start)
        if inner_end is None or not _is_just_a_frame(html[inner_start:inner_end]):
            continue
        edits.append((m.start(1), m.end(1), open_tag))
    for start, end, tag in reversed(edits):
        # Inline display:none: a site's own CSS (display:flex …) beats the
        # hidden attribute alone.
        if re.search(r'\sstyle="', tag):
            tag = re.sub(r'\sstyle="', ' style="display:none;', tag, count=1)
            tag = tag[:-1].rstrip() + " hidden>"
        else:
            tag = tag[:-1].rstrip() + ' hidden style="display:none">'
        html = html[:start] + tag + html[end:]
    return html


def _closing_index(html: str, name: str, start: int) -> Optional[int]:
    """Where the element opened just before `start` closes (nesting-aware)."""
    depth = 1
    for m in re.finditer(rf"<(/?){name}\b[^<>]*>", html[start:], re.I):
        if m.group(1):
            depth -= 1
            if depth == 0:
                return start + m.start()
        elif not m.group(0).endswith("/>"):
            depth += 1
    return None


def _is_just_a_frame(inner: str) -> bool:
    if len(re.findall(r"<img\b", inner, re.I)) != 1 or _NOT_A_FRAME.search(inner):
        return False
    text = re.sub(r"<[^>]*>", " ", inner)
    return len(" ".join(text.split())) <= _MAX_CAPTION_CHARS


def _pick(key: str, query: str, nth: int, orientation: Optional[str]) -> Optional[dict]:
    """The nth search result for a query, so a repeated description gets a
    different photo each time it appears on the page. A long, very specific
    description often finds nothing, so shorter versions are tried too."""
    for attempt in _shorter_versions(query):
        photos = _search(key, attempt, orientation)
        if photos:
            return photos[nth % len(photos)]
    return None


def _shorter_versions(query: str) -> list[str]:
    """The description itself, then its first four words. Not shorter than
    that: "papaya orange formula 1 car" cut to two words finds fruit, and no
    photo beats an obviously wrong one."""
    words = query.split()
    return [query, " ".join(words[:4])] if len(words) > 4 else [query]


def _search(key: str, query: str, orientation: Optional[str]) -> list[dict]:
    cache_key = f"{query.lower()}|{orientation}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    if _limit_nearly_used():
        logger.warning("Unsplash hourly limit nearly used up, skipping photo %r", query)
        return []
    params = {"query": query, "per_page": 5, "content_filter": "high"}
    if orientation:
        params["orientation"] = orientation
    try:
        res = httpx.get(f"{_API}/search/photos", params=params, headers=_headers(key), timeout=10)
    except httpx.HTTPError as e:
        logger.warning("Unsplash search failed for %r: %s", query, e)
        return []
    _note_remaining(res)
    if res.status_code != 200:
        logger.warning("Unsplash search %r -> %s %s", query, res.status_code, res.text[:120])
        return []
    photos = res.json().get("results", [])
    _cache[cache_key] = (time.time(), photos)
    return photos


def _track_use(key: str, photo: dict) -> None:
    """Unsplash asks to be told when a photo is used, so the photographer's
    stats count it. Best effort: a failure here never costs the user."""
    url = (photo.get("links") or {}).get("download_location")
    if not url or _limit_nearly_used():
        return
    try:
        _note_remaining(httpx.get(url, headers=_headers(key), timeout=10))
    except httpx.HTTPError:
        pass


def _with_photo(tag: str, is_bg: bool, photo: dict, lazy: bool = True) -> str:
    raw = photo["urls"]["raw"]
    sep = "&" if "?" in raw else "?"
    credit = html_lib.escape(
        f'{photo["user"]["name"]}|{photo["user"]["links"]["html"]}', quote=True
    )
    extra = f' data-photo-credit="{credit}"'
    if is_bg:
        url = f"{raw}{sep}w=1920&q=80&auto=format&fit=crop"
        style = f"background-image:url('{url}');background-size:cover;background-position:center;"
        if re.search(r'\sstyle="', tag):
            tag = re.sub(r'\sstyle="', f' style="{style}', tag, count=1)
        else:
            extra += f' style="{style}"'
    else:
        url = f"{raw}{sep}w=1200&q=80&auto=format&fit=crop"
        extra += f' src="{url}"' + (' loading="lazy"' if lazy else ' fetchpriority="high"')
        if not re.search(r'\salt="', tag):
            alt = html_lib.escape(photo.get("alt_description") or "", quote=True)
            extra += f' alt="{alt}"'
    closing = "/>" if tag.endswith("/>") else ">"
    return tag[: -len(closing)].rstrip() + extra + closing


def _with_credits(html: str) -> str:
    """(Re)build the credits line from every photo now on the page."""
    html = _CREDITS.sub("", html)
    people: dict[str, str] = {}
    for name_url in re.findall(r'data-photo-credit="([^"]*)"', html):
        name, _, url = html_lib.unescape(name_url).partition("|")
        people.setdefault(name, url)
    if not people:
        return html
    links = ", ".join(
        f'<a href="{html_lib.escape(url)}?{_UTM}" target="_blank" rel="noopener" style="{_LINK}">'
        f"{html_lib.escape(name)}</a>"
        for name, url in people.items()
    )
    block = (
        '\n<div class="vf-photo-credits" style="font:14px/1.6 system-ui,sans-serif;'
        'text-align:center;padding:14px 16px;background:#fff;color:#222">'
        f'Photos by {links} on <a href="https://unsplash.com/?{_UTM}" target="_blank" '
        f'rel="noopener" style="{_LINK}">Unsplash</a></div>'
    )
    if re.search(r"</body>", html, re.I):
        return re.sub(r"</body>", block + "\n</body>", html, count=1, flags=re.I)
    return html + block


def _headers(key: str) -> dict:
    return {"Authorization": f"Client-ID {key}", "Accept-Version": "v1"}


def _note_remaining(res: httpx.Response) -> None:
    remaining = res.headers.get("X-Ratelimit-Remaining")
    if remaining is not None and remaining.isdigit():
        _remaining.update(requests=int(remaining), at=time.time())


def _limit_nearly_used() -> bool:
    fresh = time.time() - _remaining["at"] < 60 * 60
    return fresh and _remaining["requests"] < 3
