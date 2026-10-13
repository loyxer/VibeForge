"""Placeholder generator: builds a static preview page instead of calling
Gemini, so the full pipeline (chat -> API -> live preview -> download) can
be tested without an API key. See gemini.py for the real integration.
"""
import asyncio
import html as html_lib
from collections.abc import AsyncIterator

from .base import Event, GenerationRequest, SiteGenerator

_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Preview</title>
<style>
  body {{
    font-family: system-ui, sans-serif;
    background: #12141a;
    color: #f2f2f2;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    margin: 0;
  }}
  .card {{ text-align: center; padding: 2rem; max-width: 32rem; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Mock preview</h1>
    <p>This is a placeholder — GENERATOR=mock is active.</p>
    <p><strong>Prompt:</strong> {prompt}</p>
  </div>
</body>
</html>"""


class MockGenerator(SiteGenerator):
    """Streams the placeholder page in small pieces, like a real model would,
    so the live preview can be tried out without spending any quota."""

    def __init__(self, delay: float = 0.15) -> None:
        self._delay = delay

    async def stream(self, request: GenerationRequest) -> AsyncIterator[Event]:
        page = _TEMPLATE.format(prompt=html_lib.escape(request.prompt))
        yield ("model", "mock")
        step = max(len(page) // 10, 1)
        for i in range(0, len(page), step):
            await asyncio.sleep(self._delay)
            yield ("text", page[i : i + step])
