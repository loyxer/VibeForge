"""Real site generator backed by Google Gemini's free API tier.

Setup: put GEMINI_API_KEY=... in backend/.env (gitignored, never commit it).
Get a free key at https://aistudio.google.com/apikey.
"""
import os
import re

from google import genai

from .base import GenerationRequest, GenerationResult, SiteGenerator

_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

_SYSTEM_PROMPT = """You are a website generator. Given a description, output
a single complete, self-contained HTML document: inline <style> and
<script>, no external files, no explanations, no markdown code fences —
just the raw HTML starting with <!doctype html>. If existing HTML is
provided, edit it to satisfy the new instruction instead of starting over,
preserving everything the instruction didn't ask to change."""


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

        response = self._client.models.generate_content(
            model=_MODEL,
            contents="\n\n".join(parts),
        )
        return GenerationResult(html=_extract_html(response.text))


def _extract_html(text: str) -> str:
    # The model sometimes wraps its output in a markdown code fence despite
    # being told not to — strip it if present.
    match = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL)
    return (match.group(1) if match else text).strip()
