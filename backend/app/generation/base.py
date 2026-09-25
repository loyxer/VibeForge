"""Site generator interface every backend (mock, Gemini, ...) implements."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
    def generate(self, request: GenerationRequest) -> GenerationResult:
        ...
