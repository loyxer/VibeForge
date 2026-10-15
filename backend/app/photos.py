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
            return tag  # no photo: the page's own colors show instead of a broken image
        used[query] = used.get(query, 0) + 1
        filled += 1
        _track_use(key, photo)
        # The first photo is usually the big one at the top: load it right
        # away; the rest can wait until they're scrolled near.
        return _with_photo(tag, is_bg, photo, lazy=filled > 1)

    html = _TAG.sub(replace, html)
    return _with_credits(html)


def _already_filled(tag: str, is_bg: bool) -> bool:
    if is_bg:
        return "background-image" in tag
    return re.search(r'\ssrc="[^"]+"', tag) is not None


def _pick(key: str, query: str, nth: int, orientation: Optional[str]) -> Optional[dict]:
    """The nth search result for a query, so a repeated description gets a
    different photo each time it appears on the page."""
    photos = _search(key, query, orientation)
    return photos[nth % len(photos)] if photos else None


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
        f'<a href="{html_lib.escape(url)}?{_UTM}" target="_blank" rel="noopener">'
        f"{html_lib.escape(name)}</a>"
        for name, url in people.items()
    )
    block = (
        '\n<div class="vf-photo-credits" style="font:12px/1.5 system-ui,sans-serif;'
        'text-align:center;padding:16px;opacity:.7">'
        f'Photos by {links} on <a href="https://unsplash.com/?{_UTM}" target="_blank" '
        'rel="noopener">Unsplash</a></div>'
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
