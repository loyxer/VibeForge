"""Placeholder generator: builds a static preview page instead of calling
Gemini, so the full pipeline (chat -> API -> live preview -> download) can
be tested without an API key. See gemini.py for the real integration.
"""
import html as html_lib

from .base import GenerationRequest, GenerationResult, SiteGenerator

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
    def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            html=_TEMPLATE.format(prompt=html_lib.escape(request.prompt))
        )
