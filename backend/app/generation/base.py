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
from dataclasses import dataclass
from typing import Literal, Optional

Event = tuple[Literal["status", "model", "text", "reset"], str]


@dataclass
class GenerationRequest:
    prompt: str
    previous_html: Optional[str] = None


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


def finish_html(text: str) -> str:
    """Turn the model's complete output into the HTML we store."""
    html = extract_html(text)
    if not html:
        raise RuntimeError("The AI returned an empty response — try rephrasing the request.")
    return html


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
