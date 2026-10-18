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
    {photos}
  </div>
</body>
</html>"""


_PAGES_TEMPLATE = """<!doctype html>
<html lang="uk">
<head><meta charset="utf-8"><title>Mock site</title>
<style>body{{font-family:system-ui,sans-serif;margin:0}}header,footer{{padding:16px;background:#222;color:#fff}}
nav a{{color:#fff;margin-right:16px}}nav a[aria-current="page"]{{text-decoration:underline}}section{{padding:48px 16px}}</style></head>
<body>
<header><nav><a href="#/home" data-page-link="home">Головна</a><a href="#/about" data-page-link="about">Про нас</a><a href="#/contact" data-page-link="contact">Контакти</a></nav></header>
<main>
<section data-page="home"><h1>Головна</h1><p>{prompt}</p><a href="#/contact">Написати нам</a></section>
<section data-page="about"><h1>Про нас</h1><p id="team">Наша команда.</p></section>
<section data-page="contact"><h1>Контакти</h1><p>+380 00 000 00 00</p></section>
</main>
<footer>© 2026</footer>
</body></html>"""


class MockGenerator(SiteGenerator):
    """Streams the placeholder page in small pieces, like a real model would,
    so the live preview can be tried out without spending any quota."""

    def __init__(self, delay: float = 0.15) -> None:
        self._delay = delay

    async def stream(self, request: GenerationRequest) -> AsyncIterator[Event]:
        photos = "".join(
            f'<img src="{html_lib.escape(p.url)}" alt="" style="width:30%;margin:4px">'
            for p in request.photos
        )
        template = _PAGES_TEMPLATE if request.pages else _TEMPLATE
        page = template.format(prompt=html_lib.escape(request.prompt), photos=photos)
        yield ("model", "mock")
        step = max(len(page) // 10, 1)
        for i in range(0, len(page), step):
            await asyncio.sleep(self._delay)
            yield ("text", page[i : i + step])
