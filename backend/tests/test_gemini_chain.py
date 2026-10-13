"""The Gemini model chain, exercised against a fake client — no real API
calls, no quota spent."""
import asyncio

import pytest

from app.generation import gemini
from app.generation.base import GenerationRequest
from app.generation.gemini import GeminiGenerator, ModelsBusyError, QuotaExceededError

DAILY = RuntimeError(
    "429 RESOURCE_EXHAUSTED quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
)
MINUTE = RuntimeError(
    "429 RESOURCE_EXHAUSTED quota_id: GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
)
OVERLOADED = RuntimeError("503 UNAVAILABLE The model is overloaded")
MISSING = RuntimeError("404 NOT_FOUND models/old-model is not found")
SILENT = "silent"  # sits in the queue and never sends a first chunk


class FakeChunk:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """Answers per model from a script: a list of results consumed in order
    (the last one repeats). A result is the HTML to stream back in pieces,
    an Exception to fail with, or SILENT to never answer."""

    def __init__(self, script):
        self.script = {model: list(results) for model, results in script.items()}
        self.calls = []
        self.closed = []
        self.aio = self
        self.models = self

    async def generate_content_stream(self, model, contents):
        self.calls.append(model)
        results = self.script[model]
        result = results.pop(0) if len(results) > 1 else results[0]
        return self._chunks(model, result)

    async def _chunks(self, model, result):
        try:
            if isinstance(result, Exception):
                raise result
            if result == SILENT:
                await asyncio.sleep(3600)
            if isinstance(result, tuple):  # (text written before failing, error)
                yield FakeChunk(result[0])
                raise result[1]
            for i in range(0, len(result), 5):
                yield FakeChunk(result[i : i + 5])
        finally:
            self.closed.append(model)


def make(script, timeout=0.05):
    client = FakeClient(script)
    gen = GeminiGenerator(client=client, models=tuple(script), first_chunk_timeout=timeout)
    return gen, client


REQUEST = GenerationRequest(prompt="a coffee shop")


def generate(gen):
    return asyncio.run(gen.generate(REQUEST))


def events(gen):
    async def collect():
        return [e async for e in gen.stream(REQUEST)]

    return asyncio.run(collect())


def test_first_model_wins():
    gen, client = make({"a": ["<html>a</html>"], "b": ["<html>b</html>"]})
    result = generate(gen)
    assert (result.html, result.model) == ("<html>a</html>", "a")
    assert client.calls == ["a"]


def test_streams_in_pieces():
    gen, _ = make({"a": ["<html>hello</html>"]})
    evs = events(gen)
    assert evs[0] == ("model", "a")
    texts = [value for kind, value in evs if kind == "text"]
    assert len(texts) > 1 and "".join(texts) == "<html>hello</html>"


def test_silent_model_is_abandoned_and_closed():
    gen, client = make({"slow": [SILENT], "b": ["<html>b</html>"]})
    evs = events(gen)
    assert ("model", "b") in evs
    assert evs[0][0] == "status"  # the user is told we're switching
    assert "slow" in client.closed  # the stuck request was cancelled


def test_silent_model_is_skipped_next_time():
    gen, client = make({"slow": [SILENT], "b": ["<html>b</html>"]})
    generate(gen)
    generate(gen)
    assert client.calls == ["slow", "b", "b"]


def test_drop_out_mid_stream_starts_over_with_next_model():
    gen, client = make({"a": [("<html>half", OVERLOADED)], "b": ["<html>b</html>"]})
    evs = events(gen)
    kinds = [k for k, _ in evs]
    assert kinds.index("reset") < kinds.index("model", kinds.index("reset"))
    result = generate(make({"a": [("<html>half", OVERLOADED)], "b": ["<html>b</html>"]})[0])
    assert result.html == "<html>b</html>" and result.model == "b"


def test_other_mid_stream_errors_are_not_swallowed():
    gen, _ = make({"a": [("<html>half", ValueError("broken"))], "b": ["<html>b</html>"]})
    with pytest.raises(ValueError):
        generate(gen)


def test_falls_back_when_quota_used_up():
    gen, client = make({"a": [DAILY], "b": ["<html>b</html>"]})
    assert generate(gen).html == "<html>b</html>"
    assert client.calls == ["a", "b"]


def test_exhausted_model_is_skipped_next_time():
    gen, client = make({"a": [DAILY], "b": ["<html>b</html>"]})
    generate(gen)
    generate(gen)
    assert client.calls == ["a", "b", "b"]


def test_minute_cap_skip_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    gen, client = make({"a": [MINUTE, "<html>a</html>"], "b": ["<html>b</html>"]})
    generate(gen)
    clock[0] += gemini._SKIP_AFTER_MINUTE_CAP + 1
    assert generate(gen).html == "<html>a</html>"
    assert client.calls == ["a", "b", "a"]


def test_overloaded_model_is_skipped_for_a_while(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    gen, client = make({"a": [OVERLOADED, "<html>a</html>"], "b": ["<html>b</html>"]})
    assert generate(gen).html == "<html>b</html>"
    assert generate(gen).html == "<html>b</html>"
    clock[0] += gemini._SKIP_AFTER_OVERLOAD + 1
    assert generate(gen).html == "<html>a</html>"
    assert client.calls == ["a", "b", "b", "a"]


def test_all_busy_raises_busy_error():
    gen, _ = make({"a": [OVERLOADED], "b": [SILENT]})
    with pytest.raises(ModelsBusyError):
        generate(gen)


def test_everything_skipped_asks_all_models_again():
    gen, client = make({"a": [OVERLOADED, "<html>a</html>"]})
    with pytest.raises(ModelsBusyError):
        generate(gen)
    # "a" is now skipped, but it's the only model — try it anyway.
    assert generate(gen).html == "<html>a</html>"


def test_missing_model_is_skipped():
    gen, _ = make({"old-model": [MISSING], "b": ["<html>b</html>"]})
    assert generate(gen).html == "<html>b</html>"


def test_all_exhausted_raises_quota_error():
    gen, _ = make({"a": [DAILY], "b": [MINUTE]})
    with pytest.raises(QuotaExceededError):
        generate(gen)
    # And again with everything already marked as skipped.
    with pytest.raises(QuotaExceededError):
        generate(gen)


def test_other_errors_are_not_swallowed():
    gen, client = make({"a": [ValueError("bad request")], "b": ["<html>b</html>"]})
    with pytest.raises(ValueError):
        generate(gen)
    assert client.calls == ["a"]


def test_strips_markdown_fence():
    gen, _ = make({"a": ["```html\n<html>a</html>\n```"]})
    assert generate(gen).html == "<html>a</html>"
