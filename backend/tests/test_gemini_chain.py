"""The Gemini model chain, exercised against a fake client — no real API
calls, no quota spent."""
import pytest

from app.generation import gemini
from app.generation.base import GenerationRequest
from app.generation.gemini import GeminiGenerator, QuotaExceededError

DAILY = RuntimeError(
    "429 RESOURCE_EXHAUSTED quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
)
MINUTE = RuntimeError(
    "429 RESOURCE_EXHAUSTED quota_id: GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
)
OVERLOADED = RuntimeError("503 UNAVAILABLE The model is overloaded")
MISSING = RuntimeError("404 NOT_FOUND models/old-model is not found")


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """Answers per model from a script: a list of results (str or
    Exception) consumed in order; the last one repeats."""

    def __init__(self, script):
        self.script = {model: list(results) for model, results in script.items()}
        self.calls = []
        self.models = self

    def generate_content(self, model, contents):
        self.calls.append(model)
        results = self.script[model]
        result = results.pop(0) if len(results) > 1 else results[0]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def make(script):
    client = FakeClient(script)
    return GeminiGenerator(client=client, models=tuple(script)), client


REQUEST = GenerationRequest(prompt="a coffee shop")


def test_first_model_wins():
    gen, client = make({"a": ["<html>a</html>"], "b": ["<html>b</html>"]})
    assert gen.generate(REQUEST).html == "<html>a</html>"
    assert client.calls == ["a"]


def test_falls_back_when_quota_used_up():
    gen, client = make({"a": [DAILY], "b": ["<html>b</html>"]})
    assert gen.generate(REQUEST).html == "<html>b</html>"
    assert client.calls == ["a", "b"]


def test_exhausted_model_is_skipped_next_time():
    gen, client = make({"a": [DAILY], "b": ["<html>b</html>"]})
    gen.generate(REQUEST)
    gen.generate(REQUEST)
    assert client.calls == ["a", "b", "b"]


def test_minute_cap_skip_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    gen, client = make({"a": [MINUTE, "<html>a</html>"], "b": ["<html>b</html>"]})
    gen.generate(REQUEST)
    clock[0] += gemini._SKIP_AFTER_MINUTE_CAP + 1
    assert gen.generate(REQUEST).html == "<html>a</html>"
    assert client.calls == ["a", "b", "a"]


def test_overloaded_model_is_skipped_for_a_while(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    gen, client = make({"a": [OVERLOADED, "<html>a</html>"], "b": ["<html>b</html>"]})
    assert gen.generate(REQUEST).html == "<html>b</html>"
    assert gen.generate(REQUEST).html == "<html>b</html>"
    clock[0] += gemini._SKIP_AFTER_OVERLOAD + 1
    assert gen.generate(REQUEST).html == "<html>a</html>"
    assert client.calls == ["a", "b", "b", "a"]


def test_all_overloaded_raises_the_overload_error():
    gen, _ = make({"a": [OVERLOADED], "b": [OVERLOADED]})
    with pytest.raises(RuntimeError, match="503"):
        gen.generate(REQUEST)


def test_everything_skipped_asks_all_models_again():
    gen, client = make({"a": [OVERLOADED, "<html>a</html>"]})
    with pytest.raises(RuntimeError, match="503"):
        gen.generate(REQUEST)
    # "a" is now skipped, but it's the only model — try it anyway.
    assert gen.generate(REQUEST).html == "<html>a</html>"


def test_missing_model_is_skipped():
    gen, client = make({"old-model": [MISSING], "b": ["<html>b</html>"]})
    assert gen.generate(REQUEST).html == "<html>b</html>"


def test_all_exhausted_raises_quota_error():
    gen, _ = make({"a": [DAILY], "b": [MINUTE]})
    with pytest.raises(QuotaExceededError):
        gen.generate(REQUEST)
    # And again with everything already marked as skipped.
    with pytest.raises(QuotaExceededError):
        gen.generate(REQUEST)


def test_other_errors_are_not_swallowed():
    gen, client = make({"a": [ValueError("bad request")], "b": ["<html>b</html>"]})
    with pytest.raises(ValueError):
        gen.generate(REQUEST)
    assert client.calls == ["a"]


def test_strips_markdown_fence():
    gen, _ = make({"a": ["```html\n<html>a</html>\n```"]})
    assert gen.generate(REQUEST).html == "<html>a</html>"
