"""Real site generator backed by Google Gemini's free API tier.

Setup: put GEMINI_API_KEY=... in backend/.env (gitignored, never commit it).
Get a free key at https://aistudio.google.com/apikey.

The free tier caps each model separately (e.g. 20 requests/day for every
Flash model, 500/day for the Flash Lite ones — see AI Studio → Rate
Limit), so instead of one model we walk a chain from best to cheapest:
when a model's quota is used up we move on to the next one.
"""
import logging
import os
import re
import threading
import time

from google import genai

from .base import GenerationRequest, GenerationResult, SiteGenerator

logger = logging.getLogger("vibeforge")

# Best first. Override with GEMINI_MODELS="model-a,model-b" if needed.
_DEFAULT_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)
_MODELS = tuple(
    m.strip()
    for m in os.getenv("GEMINI_MODELS", ",".join(_DEFAULT_MODELS)).split(",")
    if m.strip()
)

# A model answering 503 "high demand" gets no retry: with a whole chain of
# models it's faster to move on, and we skip it for a bit so the next
# users don't wait on it either.
_SKIP_AFTER_OVERLOAD = 2 * 60
_RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "overloaded", "high demand")
_QUOTA_MARKER = "RESOURCE_EXHAUSTED"

# How long to skip a model after it reports its quota is used up. A daily
# cap resets at midnight Pacific; rechecking hourly costs one fast failed
# call and saves us from timezone bookkeeping.
_SKIP_AFTER_DAILY_CAP = 60 * 60
_SKIP_AFTER_MINUTE_CAP = 60


class QuotaExceededError(RuntimeError):
    """Every model in the chain has used up its free-tier quota."""


_SYSTEM_PROMPT = """You are a website generator. Given a description, output
a single complete, self-contained HTML document: inline <style> and
<script>, no external files, no explanations, no markdown code fences —
just the raw HTML starting with <!doctype html>. If existing HTML is
provided, edit it to satisfy the new instruction instead of starting over,
preserving everything the instruction didn't ask to change.

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

For images, never reference a local or made-up file path (e.g. "photo.jpg",
"logo.png") — it won't exist and will show as broken. Instead use inline
SVG, CSS (gradients, shapes, icons via Unicode/emoji), or real hotlinkable
photo URLs from https://picsum.photos/<width>/<height> (optionally
https://picsum.photos/seed/<word>/<width>/<height> for a stable image).

Make it look like a real, finished product, not a wireframe: a clear
visual hierarchy, generous spacing, a coherent color palette and
typography, and modern CSS (flexbox/grid, rounded corners, subtle shadows
or gradients where they fit the theme) rather than default browser
styling."""


class GeminiGenerator(SiteGenerator):
    def __init__(self, client=None, models: tuple[str, ...] = _MODELS) -> None:
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
        # model -> time.monotonic() until which we don't bother trying it
        # (out of quota, overloaded, or no longer exists)
        self._skip_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        parts = [_SYSTEM_PROMPT]
        if request.previous_html:
            parts.append(f"Existing HTML:\n{request.previous_html}")
        parts.append(f"Instruction: {request.prompt}")
        contents = "\n\n".join(parts)

        last_error: Exception | None = None
        for model in self._available_models():
            try:
                html = self._generate_with(model, contents)
                logger.info("Generated with %s", model)
                return GenerationResult(html=html)
            except Exception as e:  # noqa: BLE001 - SDK error types vary
                last_error = e
                if _QUOTA_MARKER in str(e):
                    self._mark_exhausted(model, e)
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
                    continue
                raise

        if last_error is None or _QUOTA_MARKER in str(last_error):
            raise QuotaExceededError(
                "Daily free generation limit reached — try again tomorrow."
            ) from last_error
        raise last_error

    def _generate_with(self, model: str, contents: str) -> str:
        response = self._client.models.generate_content(model=model, contents=contents)
        html = _extract_html(response.text or "")
        if not html:
            raise RuntimeError(
                "Gemini returned an empty response — try rephrasing the request."
            )
        return html

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


def _extract_html(text: str) -> str:
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
