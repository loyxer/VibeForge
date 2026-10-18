"""AI logos, drawn as SVG by the free text model.

The model never writes the finished logo. It only invents three *concepts*
as JSON — a symbol (a small SVG, no text), colors, a font style, a tagline —
and we build the logo from them with a fixed template. That way the name is
always set at an exact width (no text cut off, however the model counts
letters), and everything that reaches a page passes `clean_svg` first: an
allow-list of shapes and attributes, so a logo can never carry a script, an
event handler or a link to somewhere else.

`with_logo` puts the chosen logo into the site's header, in place of the
text name (or, failing that, at the top), and can be repeated to swap it.
"""
import json
import logging
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from html import escape
from html.parser import HTMLParser
from typing import Any, Optional

logger = logging.getLogger("vibeforge")

MAX_NAME = 40
MAX_BRIEF = 300
MAX_SVG = 12_000

# One person can ask for 12 sets an hour: each one is a request to the shared
# free quota of the AI.
_LIMIT, _WINDOW = 12, 3600


class LogoError(RuntimeError):
    pass


class TooMany(LogoError):
    pass


# ------------------------------------------------------------ cleaning SVG

_SVG_NS = "{http://www.w3.org/2000/svg}"
_SHAPES = {"g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
_NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"
_PLAIN = {
    "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "width", "height",
    "stroke-width", "stroke-miterlimit", "opacity", "fill-opacity", "stroke-opacity",
    "font-size", "textLength",
}
_NUM_VALUE = re.compile(rf"^{_NUM}(?:%|px)?$")
_LIST = {
    "points": re.compile(r"^[-\d\s.,eE+]*$"),
    "d": re.compile(r"^[MmLlHhVvCcSsQqTtAaZz\d\s.,eE+-]*$"),
    "viewBox": re.compile(rf"^{_NUM}[\s,]+{_NUM}[\s,]+{_NUM}[\s,]+{_NUM}$"),
    "transform": re.compile(
        r"^(?:(?:translate|scale|rotate|skewX|skewY|matrix)\([-\d\s.,eE+]*\)\s*)+$"
    ),
}
_PAINT = re.compile(
    r"^(?:none|currentColor|#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%]+\)|[a-zA-Z]{3,20})$"
)
_WORDS = {
    "stroke-linecap": {"butt", "round", "square"},
    "stroke-linejoin": {"miter", "round", "bevel"},
    "fill-rule": {"nonzero", "evenodd"},
    "clip-rule": {"nonzero", "evenodd"},
    "text-anchor": {"start", "middle", "end"},
    "lengthAdjust": {"spacing", "spacingAndGlyphs"},
}
_TEXT_ONLY = {"font-family", "font-weight", "letter-spacing"}
_FONT_FAMILY = re.compile(r"^[\w\s,'\"-]{1,120}$")


def _attr_ok(name: str, value: str) -> bool:
    if len(value) > 6000:
        return False
    if name in _PLAIN:
        return bool(_NUM_VALUE.match(value))
    if name in _LIST:
        return bool(_LIST[name].match(value))
    if name in ("fill", "stroke"):
        return bool(_PAINT.match(value))
    if name in _WORDS:
        return value in _WORDS[name]
    if name == "font-family":
        return bool(_FONT_FAMILY.match(value))
    if name == "font-weight":
        return value in {"400", "500", "600", "700", "800", "900", "bold", "normal"}
    if name == "letter-spacing":
        return bool(_NUM_VALUE.match(value))
    return False


def clean_svg(svg: str, allow_text: bool = True) -> Optional[str]:
    """The SVG rebuilt from an allow-list of shapes and attributes, or None if
    it isn't a simple, safe SVG. Nothing is kept that isn't named here."""
    if not isinstance(svg, str) or len(svg) > MAX_SVG:
        return None
    lowered = svg.lower()
    if "<!doctype" in lowered or "<!entity" in lowered or "<?" in lowered.replace("<?xml", ""):
        return None
    try:
        root = ET.fromstring(svg.strip())
    except ET.ParseError:
        return None
    if root.tag.removeprefix(_SVG_NS) != "svg":
        return None
    count = 0
    allowed = _SHAPES | ({"text"} if allow_text else set())

    def build(el: ET.Element, depth: int) -> Optional[str]:
        nonlocal count
        tag = el.tag.removeprefix(_SVG_NS) if isinstance(el.tag, str) else ""
        if tag not in allowed or depth > 6:
            return None  # unknown things are dropped, with everything inside
        count += 1
        if count > 80:
            raise ValueError("too many elements")
        attrs = []
        for key, value in el.attrib.items():
            if key.startswith("{") or key in ("id", "class", "style"):
                continue
            if key in _TEXT_ONLY and tag != "text":
                continue
            if _attr_ok(key, value.strip()):
                attrs.append(f' {key}="{escape(value.strip(), quote=True)}"')
        if tag == "text":
            text = "".join(el.itertext()).strip()
            if not text or len(text) > 80:
                return None
            return f"<text{''.join(attrs)}>{escape(text)}</text>"
        inner = "".join(filter(None, (build(child, depth + 1) for child in el)))
        return f"<{tag}{''.join(attrs)}>{inner}</{tag}>"

    try:
        inner = "".join(filter(None, (build(child, 1) for child in root)))
    except ValueError:
        return None
    if not inner:
        return None
    view_box = root.attrib.get("viewBox", "").strip()
    if not _LIST["viewBox"].match(view_box):
        return None
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{escape(view_box)}">{inner}</svg>'
    )


# ---------------------------------------------------------------- composing

# font stack, weight, average letter width as a share of the font size
_FONTS = {
    "serif": ("Georgia, 'Times New Roman', serif", "700", 0.56),
    "sans": ("'Helvetica Neue', Arial, sans-serif", "800", 0.60),
    "rounded": ("'Trebuchet MS', 'Segoe UI', Arial, sans-serif", "700", 0.58),
    "display": ("'Arial Black', Impact, sans-serif", "900", 0.66),
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_TEXT_WIDTH = 380


def compose(name: str, concept: dict[str, Any], dark: bool = False) -> Optional[str]:
    """The finished logo (symbol on the left, name and tagline on the right)
    from one concept, or None if its symbol isn't usable."""
    icon = clean_svg(str(concept.get("icon", "")), allow_text=False)
    if not icon:
        return None
    vb = [float(n) for n in re.findall(_NUM, re.search(r'viewBox="([^"]*)"', icon).group(1))]
    scale = 100 / max(vb[2], vb[3], 1)
    dx = (100 - vb[2] * scale) / 2 - vb[0] * scale
    dy = (100 - vb[3] * scale) / 2 - vb[1] * scale
    body = icon[icon.index(">") + 1 : -len("</svg>")]

    font, weight, k = _FONTS.get(str(concept.get("font")), _FONTS["sans"])
    caps = bool(concept.get("caps"))
    title = (name.upper() if caps else name).strip()
    tagline = str(concept.get("tagline") or "").strip()[:40]
    if caps:
        tagline = tagline.upper()
    color = str(concept.get("color") or "")
    color = color if _HEX.match(color) else ("#f5f5f5" if dark else "#222222")

    wide = k * (1.12 if caps else 1)
    size = max(min(46, _MAX_TEXT_WIDTH / (len(title) * wide)), 20)
    title_w = round(len(title) * size * wide)
    tag_size = 16
    tag_w = min(round(len(tagline) * tag_size * 0.62 * (1.1 if caps else 1)), _MAX_TEXT_WIDTH)
    title_y = 56 if tagline else 50 + round(size * 0.35)
    parts = [
        f'<g transform="translate({dx:.2f} {dy:.2f}) scale({scale:.4f})">{body}</g>',
        f'<text x="120" y="{title_y}" font-family="{escape(font, quote=True)}" font-size="{size:.1f}" '
        f'font-weight="{weight}" fill="{color}" textLength="{title_w}" '
        f'lengthAdjust="spacingAndGlyphs">{escape(title)}</text>',
    ]
    if tagline:
        parts.append(
            f'<text x="121" y="84" font-family="{escape(font, quote=True)}" font-size="{tag_size}" '
            f'font-weight="600" fill="{color}" opacity="0.8" letter-spacing="1" textLength="{tag_w}" '
            f'lengthAdjust="spacingAndGlyphs">{escape(tagline)}</text>'
        )
    width = 120 + max(title_w, tag_w) + 4
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 100">{"".join(parts)}</svg>'
    )
    return clean_svg(svg)  # the finished logo passes the same check as any other


# ------------------------------------------------------------ the AI's part

_PROMPT = """You design logo concepts for a small business website.
Business name: "{name}"
Description / wishes: "{brief}"
The logo is placed in the page header on a {mode} background.

Return a JSON array of exactly 3 clearly different concepts and nothing else.
Each concept is an object with:
- "icon": an SVG of just the symbol — no text, no letters. It must start with
  <svg viewBox="0 0 100 100"> and use only simple flat shapes (path, circle,
  ellipse, rect, polygon, line), at most 3 colors, no gradients, no filters,
  no external references. Draw it inside the box with a small margin; make it
  recognisable and relevant to the business.
- "color": hex color (like "#2b2b2b") for the business name, with strong
  contrast against the {mode} background.
- "font": one of "serif", "sans", "rounded", "display".
- "caps": true to write the name in capital letters, otherwise false.
- "tagline": a short descriptor of 1-4 words in the language of the name, or "".
The three concepts must differ in symbol idea, palette and font."""

_MODEL_ORDER = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")
_client = None
_client_lock = threading.Lock()


def _gemini():
    global _client
    with _client_lock:
        if _client is None:
            from google import genai
            from google.genai import types

            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise LogoError("GEMINI_API_KEY not set")
            _client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=40_000))
        return _client


def _ask_gemini(name: str, brief: str, dark: bool) -> list[dict[str, Any]]:
    from google.genai import types

    prompt = _PROMPT.format(name=name, brief=brief or "—", mode="dark" if dark else "light")
    last: Optional[Exception] = None
    for model in _MODEL_ORDER:
        try:
            res = _gemini().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=1.0
                ),
            )
            data = json.loads(res.text)
            if isinstance(data, list) and data:
                return [c for c in data if isinstance(c, dict)]
        except Exception as e:  # noqa: BLE001 - SDK error types vary
            last = e
            logger.warning("Logo concepts from %s failed: %s", model, str(e)[:200])
    raise LogoError(f"busy: {last}")


def _mock_concepts(name: str, brief: str, dark: bool) -> list[dict[str, Any]]:
    ink = "#f5f5f5" if dark else "#1c1c1c"
    return [
        {"icon": '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#ff9f1c"/>'
                 '<circle cx="50" cy="50" r="16" fill="#1c1c1c"/></svg>',
         "color": ink, "font": "rounded", "caps": False, "tagline": "студія"},
        {"icon": '<svg viewBox="0 0 100 100"><rect x="14" y="14" width="72" height="72" rx="16" '
                 'fill="#1479b8"/><polygon points="50,28 72,68 28,68" fill="#fff"/></svg>',
         "color": ink, "font": "serif", "caps": True, "tagline": ""},
        {"icon": '<svg viewBox="0 0 100 100"><polygon points="50,8 88,30 88,70 50,92 12,70 12,30" '
                 'fill="#58cc02"/></svg>',
         "color": ink, "font": "display", "caps": False, "tagline": "з 2026"},
    ]


def make(name: str, brief: str, dark: bool, user: str) -> list[str]:
    """Up to three finished logos (SVG) for the business."""
    name, brief = name.strip()[:MAX_NAME], brief.strip()[:MAX_BRIEF]
    if len(name) < 2:
        raise LogoError("Write the business name first")
    _rate_limit(user)
    concepts = (
        _ask_gemini(name, brief, dark)
        if os.getenv("GENERATOR", "mock").lower() == "gemini"
        else _mock_concepts(name, brief, dark)
    )
    logos = [svg for c in concepts[:3] if (svg := compose(name, c, dark))]
    if not logos:
        raise LogoError("busy: no usable concepts")
    return logos


_recent: dict[str, deque] = defaultdict(deque)
_recent_lock = threading.Lock()


def _rate_limit(user: str) -> None:
    now = time.monotonic()
    with _recent_lock:
        q = _recent[user]
        while q and now - q[0] > _WINDOW:
            q.popleft()
        if len(q) >= _LIMIT:
            raise TooMany("Too many logo requests — try again in a while")
        q.append(now)


# ----------------------------------------------------- putting it on a site

LOGO_STYLE = (
    '<style id="vf-logo-style">.vf-logo{display:block;height:50px;width:auto;max-width:100%}'
    ".vf-logo-wrap{padding:12px 16px}</style>"
)
_VOID = {"img", "br", "hr", "input", "meta", "link", "source", "area", "base", "col", "embed", "wbr"}
_LOGOISH = {"logo", "brand", "logotype", "wordmark"}
_CANDIDATE_TAGS = {"a", "div", "span", "h1", "h2", "h3", "p", "strong", "b", "figure", "img"}
_HOMEISH = {"#", "/", "#/home", "#home", "#top", "index.html", "./"}
_NOT_A_LOGO = re.compile(r"<(?:ul|ol|li|nav|form|button|input|select)\b", re.I)


class _Element:
    def __init__(self, tag: str, attrs: dict[str, str], start: int, open_end: int, ancestors: tuple):
        self.tag, self.attrs, self.start, self.open_end = tag, attrs, start, open_end
        self.ancestors = ancestors
        self.close_start = self.close_end = None  # filled in by the closing tag


class _Scan(HTMLParser):
    """Records where each element starts and ends in the source text."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_starts = [0]
        for m in re.finditer("\n", source):
            self.line_starts.append(m.end())
        self.elements: list[_Element] = []
        self.stack: list[_Element] = []
        self.feed(source)

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self._offset()
        end = start + len(self.get_starttag_text() or "")
        el = _Element(tag, {k: v or "" for k, v in attrs}, start, end,
                      tuple(e.tag for e in self.stack))
        self.elements.append(el)
        if tag not in _VOID:
            self.stack.append(el)
        else:
            el.close_start = el.close_end = end

    def handle_startendtag(self, tag, attrs):
        start = self._offset()
        end = start + len(self.get_starttag_text() or "")
        el = _Element(tag, {k: v or "" for k, v in attrs}, start, end,
                      tuple(e.tag for e in self.stack))
        el.close_start = el.close_end = end
        self.elements.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag:
                el = self.stack[i]
                del self.stack[i:]
                at = self._offset()
                el.close_start = at
                gt = self.source.find(">", at)
                el.close_end = gt + 1 if gt >= 0 else len(self.source)
                return


def _find_spot(html: str) -> Optional[tuple[str, int, int]]:
    """Where the logo goes: ("inner", from, to) to fill an element,
    ("replace", from, to) to swap a whole one, or ("insert", at, at)."""
    scan = _Scan(html)
    done = [e for e in scan.elements if e.close_end is not None]

    def plausible(e: _Element) -> bool:
        inner = html[e.open_end : e.close_start] if e.tag not in _VOID else ""
        return not _NOT_A_LOGO.search(inner) and len(re.sub(r"<[^>]*>", "", inner)) < 200

    for e in done:
        if e.tag not in _CANDIDATE_TAGS or "footer" in e.ancestors or "svg" in e.ancestors:
            continue
        if "head" in e.ancestors:
            continue
        words = set(re.split(r"[\s_-]+", f"{e.attrs.get('class', '')} {e.attrs.get('id', '')}".lower()))
        if words & _LOGOISH and plausible(e):
            if e.tag == "img":
                return ("replace", e.start, e.close_end)
            return ("inner", e.open_end, e.close_start)
    for e in done:
        if (
            e.tag == "a"
            and ("header" in e.ancestors or "nav" in e.ancestors)
            and e.attrs.get("href", "").strip().lower() in _HOMEISH
            and plausible(e)
        ):
            return ("inner", e.open_end, e.close_start)
    for tag in ("header", "nav"):
        for e in done:
            if e.tag == tag and "footer" not in e.ancestors:
                return ("insert", e.open_end, e.open_end)
    body = next((e for e in scan.elements if e.tag == "body"), None)
    return ("insert", body.open_end, body.open_end) if body else None


def with_logo(html: str, svg: str) -> str:
    """The page with the logo in its header. Cleans the SVG again: whatever
    came from the browser is never trusted."""
    safe = clean_svg(svg)
    if not safe:
        raise LogoError("That isn't a valid logo")
    safe = safe.replace("<svg ", '<svg id="vf-logo" class="vf-logo" role="img" ', 1)
    old = re.search(r'<svg\b[^>]*\bid="vf-logo"[^>]*>.*?</svg>', html, re.S)
    if old:
        html = html[: old.start()] + safe + html[old.end() :]
    else:
        spot = _find_spot(html)
        if spot is None:
            html = f'<div class="vf-logo-wrap">{safe}</div>' + html
        else:
            kind, a, b = spot
            if kind == "insert":
                safe = f'<div class="vf-logo-wrap">{safe}</div>'
            html = html[:a] + safe + html[b:]
    if 'id="vf-logo-style"' not in html:
        head = re.search(r"</head>", html, re.I)
        at = head.start() if head else 0
        html = html[:at] + LOGO_STYLE + html[at:]
    return html
