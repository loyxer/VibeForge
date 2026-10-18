"""Real site generator backed by Google Gemini's free API tier.

Setup: put GEMINI_API_KEY=... in backend/.env (gitignored, never commit it).
Get a free key at https://aistudio.google.com/apikey.

The free tier caps each model separately (e.g. 20 requests/day for every
Flash model, 500/day for the Flash Lite ones — see AI Studio → Rate
Limit), so instead of one model we walk a chain from best to cheapest.
A model is skipped when its quota is used up, when it answers 503 "high
demand", or when it sits in Google's queue without saying anything: on the
free tier a busy model can keep a request waiting for minutes before the
first word, so we give each one FIRST_CHUNK_TIMEOUT seconds to start.
"""
import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncIterator

from google import genai

from . import base
from .base import Event, GenerationRequest, SiteGenerator

logger = logging.getLogger("vibeforge")

# Best first. Override with GEMINI_MODELS="model-a,model-b" if needed.
_DEFAULT_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)
_MODELS = tuple(
    m.strip()
    for m in os.getenv("GEMINI_MODELS", ",".join(_DEFAULT_MODELS)).split(",")
    if m.strip()
)

# Seconds a model gets to send its first piece of output. A healthy model
# starts within a few seconds; one stuck in the queue is cancelled (closing
# the request cancels it on Google's side too) and we try the next.
FIRST_CHUNK_TIMEOUT = float(os.getenv("GEMINI_FIRST_CHUNK_TIMEOUT", "15"))

# How long to leave a model alone after it let us down, so the next users
# go straight to one that works.
_SKIP_AFTER_SLOW = 5 * 60
_SKIP_AFTER_OVERLOAD = 2 * 60  # answered 503 "high demand"
_SKIP_AFTER_DAILY_CAP = 60 * 60  # resets at midnight Pacific; recheck hourly
_SKIP_AFTER_MINUTE_CAP = 60

_RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "overloaded", "high demand")
_QUOTA_MARKER = "RESOURCE_EXHAUSTED"

_BUSY_STATUS = "The AI is busy right now — trying another model…"


class QuotaExceededError(RuntimeError):
    """Every model in the chain has used up its free-tier quota."""


class ModelsBusyError(RuntimeError):
    """Every model was overloaded or stuck in the queue."""


_SYSTEM_PROMPT = """You are an expert web designer and front-end developer.
Given a description, output a single complete, self-contained HTML
document: inline <style> and <script>, no explanations, no markdown code
fences — just the raw HTML starting with <!doctype html>. The only external
resources allowed are Google Fonts (a <link> to fonts.googleapis.com) and
the photos our server adds (see below). If existing HTML is provided, edit it
to satisfy the new instruction instead of starting over, preserving
everything the instruction didn't ask to change.

This is a SINGLE page — there are no other pages or files to link to.
Never use <a href> or forms pointing at other HTML files, real external
URLs, or routes ("shop.html", "/about", "https://..."); clicking those in
the preview just shows a blank page. Every interactive element must do
something inside this same document instead: scroll to an in-page section
(href="#section-id"), toggle/reveal content via inline JS, open a modal
built into the page, etc. If a button doesn't have a real in-page action,
make it visually inert (no href, no onclick) rather than a dead link.

The page renders inside a sandboxed iframe with no access to its own
origin. Never use localStorage, sessionStorage, indexedDB, or cookies —
reading or writing them throws an error there and can silently stop the
rest of the page's JavaScript from running. Keep any "remember this"
behavior in a plain in-memory JS variable instead, scoped to the current
page view.

Language: write every piece of visible text in the language the request
itself is written in — an English request gets an English site, a Spanish
one a Spanish site, and so on — even if the subject is set in another
country. Use realistic, specific content that fits the subject —
believable names, prices, features, opening hours — never lorem ipsum or
"Feature 1 / Feature 2".

Build a complete, substantial page, not a stub: at least five distinct
sections that make sense for the subject (for example hero, about,
services or menu with prices, gallery or testimonials, contact and
footer), each with real content.

Design quality matters most. Aim for what a good designer would ship:
- A clear visual concept for this particular subject, committed to fully,
  rather than a generic template.
- Typography: one or two Google Fonts that suit the mood (for example a
  characterful display font for headings and a clean sans-serif for text),
  with a confident type scale — big, tight headlines.
- Color: a deliberate palette (background, text, one or two accents) used
  consistently, with enough contrast to read easily.
- Layout: generous whitespace, a consistent spacing rhythm, aligned grids,
  varied section layouts (not the same card grid repeated), fully
  responsive down to phone widths (see Phones below).
- Polish: hover states, smooth transitions, at most one tasteful
  animation. All content must be visible as soon as the page loads —
  never hide it (opacity: 0, off-screen transforms) waiting for a scroll
  or a script to reveal it.

Phones: many visitors are on a phone, so before you finish, check the page
at 375px wide:
- Nothing may be wider than the screen. No fixed px widths or min-widths on
  containers, text or rows of buttons; grids collapse to one column (e.g.
  repeat(auto-fit, minmax(min(100%, 260px), 1fr))); rows of buttons, chips
  or tabs wrap (flex-wrap: wrap); headlines shrink with clamp(); long
  words wrap (overflow-wrap: anywhere).
- If the navigation links are hidden on small screens, the header must have
  a menu button (☰) that opens and closes them with a few lines of JS.
  Never hide the menu with nothing to replace it. The opened menu must not
  cover that button (give the button position: relative and a higher
  z-index than the menu), so the same button can close it again; tapping
  a menu link closes it too.

JavaScript must never crash: one error stops every script on the page. Run
setup code after the page has loaded, check that an element exists before
using it, and never read event.target in a function that is also called
without an event (e.g. to set the initial state).

Photos: you can't know any real photo URLs, so never write one (and never
a made-up file path like "photo.jpg"). Instead describe each photo and our
server fills in a real, matching one from Unsplash after you finish:
- for an image: <img data-photo="latte art on a wooden table" alt="...">
  with NO src attribute;
- for a background photo: put data-photo-bg="old town street at dusk" on
  the element and give it background-size: cover and a background-position
  in your CSS, but no url() — and keep text on it readable with a dark
  overlay or text shadow.
Each description is a short English search phrase of 2–4 common words,
main subject first ("red race car", "wedding rings", "cafe interior") —
long or unusual phrases find nothing. Describe things generically, without
brand or team names: these are stock photos, they can't show a specific
company's product. Use photos where they genuinely
help — places, food, people, products, atmosphere — typically 3–6 per page.
When editing a page, keep every existing photo (tags that already have a
src or background-image) exactly as it is unless asked to change it, and
keep any element with class "vf-photo-credits" and the <style id="vf-safety">
untouched. Never try to
draw complex real-world things — phones, laptops, cars, people, animals,
food, buildings — out of CSS or SVG shapes: it always looks crude; use a
photo or leave it out. Small icons as simple inline SVGs (or emoji) are
fine."""


class GeminiGenerator(SiteGenerator):
    def __init__(
        self,
        client=None,
        models: tuple[str, ...] = _MODELS,
        first_chunk_timeout: float = FIRST_CHUNK_TIMEOUT,
    ) -> None:
        if client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY not set — add it to backend/.env "
                    "(see README for how to get a free key)."
                )
            client = genai.Client(api_key=api_key)
        self._client = client
        self._models = models
        self._first_chunk_timeout = first_chunk_timeout
        # model -> time.monotonic() until which we don't bother trying it
        self._skip_until: dict[str, float] = {}
        self._lock = threading.Lock()

    async def stream(self, request: GenerationRequest) -> AsyncIterator[Event]:
        today = base.today()
        parts = [
            _SYSTEM_PROMPT,
            f"Today is {today.isoformat()}: use {today.year} as the current year "
            "(copyright notices, \"this season\", upcoming dates).",
        ]
        if request.style:
            parts.append(f"Visual style for this site: {request.style}")
        if request.previous_html:
            parts.append(f"Existing HTML:\n{request.previous_html}")
        parts.append(f"Instruction: {request.prompt}")
        contents = "\n\n".join(parts)

        failures: list[str] = []  # "quota" / "busy", to pick the final error
        last_error: Exception | None = None
        for model in self._available_models():
            try:
                chunks, first = await self._start(model, contents)
            except TimeoutError:
                logger.warning(
                    "%s said nothing for %ss (queued), trying the next model",
                    model, self._first_chunk_timeout,
                )
                self._skip(model, _SKIP_AFTER_SLOW)
                failures.append("busy")
                yield ("status", _BUSY_STATUS)
                continue
            except Exception as e:  # noqa: BLE001 - SDK error types vary
                last_error = e
                if _QUOTA_MARKER in str(e):
                    self._mark_exhausted(model, e)
                    failures.append("quota")
                    continue
                if "NOT_FOUND" in str(e):
                    # Google retired or renamed this model — don't let one
                    # stale name in the chain take the whole site down.
                    logger.error("%s not found, skipping it: %s", model, e)
                    self._skip(model, _SKIP_AFTER_DAILY_CAP)
                    continue
                if _is_retryable(e):
                    logger.warning("%s overloaded, trying the next model", model)
                    self._skip(model, _SKIP_AFTER_OVERLOAD)
                    failures.append("busy")
                    yield ("status", _BUSY_STATUS)
                    continue
                raise

            logger.info("Generating with %s", model)
            yield ("model", model)
            try:
                if first.text:
                    yield ("text", first.text)
                async for chunk in chunks:
                    if chunk.text:
                        yield ("text", chunk.text)
            except Exception as e:  # noqa: BLE001
                # Under heavy load Google sometimes cuts a stream off halfway
                # with a 503. Half a page is useless — start over elsewhere.
                if not (_is_retryable(e) or _QUOTA_MARKER in str(e)):
                    raise
                last_error = e
                logger.warning("%s dropped out mid-stream (%s), starting over", model, e)
                self._skip(model, _SKIP_AFTER_OVERLOAD)
                failures.append("busy")
                yield ("reset", "")
                yield ("status", "The AI dropped out halfway — starting over with another model…")
                continue
            return

        if "busy" in failures:
            raise ModelsBusyError(
                "All AI models are busy right now — please try again in a few minutes."
            ) from last_error
        if failures or last_error is None:
            # Only quota failures left. Shared by every user, unlike the
            # personal limit in usage.py — say so, or someone with all 5
            # attempts left is just confused.
            raise QuotaExceededError(
                "VibeForge has used up today's free AI capacity for everyone — "
                "please try again tomorrow."
            ) from last_error
        raise last_error  # every model was missing (NOT_FOUND)

    async def _start(self, model: str, contents: str):
        """Open a stream and wait for its first chunk, within the timeout.

        Raises TimeoutError if the model stays silent; the half-open request
        is cancelled and closed so it doesn't keep running on Google's side.
        """
        opened = []

        async def first_chunk():
            chunks = await self._client.aio.models.generate_content_stream(
                model=model, contents=contents
            )
            opened.append(chunks)
            try:
                return chunks, await anext(chunks)
            except StopAsyncIteration:
                raise RuntimeError(
                    "The AI returned an empty response — try rephrasing the request."
                )

        try:
            return await asyncio.wait_for(first_chunk(), self._first_chunk_timeout)
        except TimeoutError:
            for chunks in opened:
                try:
                    await chunks.aclose()
                except Exception:  # noqa: BLE001 - best effort cleanup
                    pass
            raise

    def _available_models(self) -> list[str]:
        now = time.monotonic()
        with self._lock:
            available = [m for m in self._models if self._skip_until.get(m, 0) <= now]
        # Skips are only a shortcut — if every model is currently skipped,
        # ask them all again rather than failing without asking anyone.
        return available or list(self._models)

    def _mark_exhausted(self, model: str, error: Exception) -> None:
        daily = "PerDay" in str(error)
        skip = _SKIP_AFTER_DAILY_CAP if daily else _SKIP_AFTER_MINUTE_CAP
        logger.warning(
            "%s out of %s quota, skipping it for %ds",
            model, "daily" if daily else "per-minute", skip,
        )
        self._skip(model, skip)

    def _skip(self, model: str, seconds: int) -> None:
        with self._lock:
            self._skip_until[model] = time.monotonic() + seconds


def _is_retryable(error: Exception) -> bool:
    message = str(error)
    return any(marker in message for marker in _RETRYABLE_MARKERS)
