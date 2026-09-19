"""Real site generator backed by Google Gemini's free API tier.

Setup: put GEMINI_API_KEY=... in backend/.env (gitignored, never commit it).
Get a free key at https://aistudio.google.com/apikey.
"""
import os
import re
import time

from google import genai

from .base import GenerationRequest, GenerationResult, SiteGenerator

_MAX_RETRIES = 5
_RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "overloaded", "high demand")
_QUOTA_MARKER = "RESOURCE_EXHAUSTED"

_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


class QuotaExceededError(RuntimeError):
    """Gemini's free-tier daily request quota is used up for today."""

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
make it visually inert (no href, no onclick) rather than a dead link."""


class GeminiGenerator(SiteGenerator):
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set — add it to backend/.env "
                "(see README for how to get a free key)."
            )
        self._client = genai.Client(api_key=api_key)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        parts = [_SYSTEM_PROMPT]
        if request.previous_html:
            parts.append(f"Existing HTML:\n{request.previous_html}")
        parts.append(f"Instruction: {request.prompt}")

        contents = "\n\n".join(parts)

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=_MODEL,
                    contents=contents,
                )
                html = _extract_html(response.text or "")
                if not html:
                    raise RuntimeError(
                        "Gemini returned an empty response — try rephrasing "
                        "the request."
                    )
                return GenerationResult(html=html)
            except Exception as e:  # noqa: BLE001 - SDK error types vary
                last_error = e
                if _QUOTA_MARKER in str(e):
                    # Daily cap, not a transient overload — retrying won't
                    # help until it resets, so fail fast with a clear reason.
                    raise QuotaExceededError(
                        "Daily free generation limit reached — try again "
                        "tomorrow."
                    ) from e
                if not _is_retryable(e) or attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)  # 1s, 2s, 4s

        raise last_error  # unreachable, satisfies type checkers


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
