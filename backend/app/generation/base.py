"""Site generator interface every backend (mock, Gemini, ...) implements.

Generators stream: `stream()` is an async iterator of events

    ("status", text)  something worth telling the user while they wait
    ("model", name)   the model that is about to write the site
    ("text", chunk)   the next piece of the HTML
    ("reset", "")     the model dropped out halfway: forget the text so far,
                      another model starts over (followed by a new "model")

so the preview can build up live instead of after minutes of silence.
"""
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from . import languages
from app.user_photos import AttachedPhoto

Event = tuple[Literal["status", "model", "text", "reset"], str]


@dataclass
class GenerationRequest:
    prompt: str
    previous_html: Optional[str] = None
    style: Optional[str] = None  # design direction, see styles.py
    # The person's own photos to put on the page (app/user_photos.py).
    photos: list[AttachedPhoto] = field(default_factory=list)
    # Ukrainian + English with a switcher (see languages.py).
    bilingual: bool = False


@dataclass
class GenerationResult:
    html: str
    model: str = "unknown"  # which model produced it, for usage stats


class SiteGenerator(ABC):
    @abstractmethod
    def stream(self, request: GenerationRequest) -> AsyncIterator[Event]:
        ...

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """The whole result at once — for tests and one-off scripts."""
        model, parts = "unknown", []
        async for kind, value in self.stream(request):
            if kind == "model":
                model = value
            elif kind == "text":
                parts.append(value)
            elif kind == "reset":
                parts.clear()
        return GenerationResult(html=finish_html("".join(parts)), model=model)


def today() -> date:
    return datetime.now(ZoneInfo("Europe/Kyiv")).date()


def finish_html(text: str) -> str:
    """Turn the model's complete output into the HTML we store."""
    html = extract_html(text)
    if not html:
        raise RuntimeError("The AI returned an empty response — try rephrasing the request.")
    return languages.with_languages(with_safety_css(current_copyright_year(html)))


# A safety net for what the AI most often gets wrong on phones: one element
# wider than the screen makes the whole page slide sideways, and a big image
# without a width limit does the same.
SAFETY_CSS = (
    '<style id="vf-safety">html,body{overflow-x:clip}'
    "img,video,iframe{max-width:100%}</style>"
)


def with_safety_css(html: str) -> str:
    if 'id="vf-safety"' in html:
        return html
    for pattern in (r"</head>", r"<body\b[^>]*>"):
        m = re.search(pattern, html, re.I)
        if m:
            at = m.start() if pattern == r"</head>" else m.end()
            return html[:at] + SAFETY_CSS + html[at:]
    return html


# "© 2023 Coffee Co." — the AI doesn't know what year it is.
_COPYRIGHT_YEAR = re.compile(r"((?:©|&copy;|Copyright)\s*)(20\d\d)\b(?!\s*[–—-]\s*\d)", re.I)


def current_copyright_year(html: str) -> str:
    year = today().year

    def fix(m: re.Match) -> str:
        return m.group(1) + str(year) if int(m.group(2)) < year else m.group(0)

    return _COPYRIGHT_YEAR.sub(fix, html)


def extract_html(text: str) -> str:
    # The model sometimes wraps its whole response in a markdown code fence
    # despite being told not to — strip it if the *entire* response is
    # fenced. Deliberately anchored to the start/end (not a mid-text
    # search): the generated HTML can itself contain ``` sequences (e.g.
    # inside a JS template literal), and an unanchored search could match
    # those instead of the real fence, silently truncating the page.
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
