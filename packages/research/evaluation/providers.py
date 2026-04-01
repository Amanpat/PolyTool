"""RIS v1 evaluation gate — LLM provider abstraction.

Providers are responsible for scoring a document against the evaluation rubric.
ManualProvider is the default — it returns a placeholder score so the pipeline
works with zero external dependencies.

Cloud providers (gemini, deepseek) deferred to RIS v2. See RIS_03_EVALUATION_GATE.md.
"""

from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod

from packages.research.evaluation.types import EvalDocument


class EvalProvider(ABC):
    """Abstract base class for evaluation providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string."""
        ...

    @abstractmethod
    def score(self, doc: EvalDocument, prompt: str) -> str:
        """Score a document against the evaluation rubric.

        Args:
            doc: The document to evaluate.
            prompt: The full scoring prompt (from build_scoring_prompt).

        Returns:
            Raw JSON string with scoring dimensions.
        """
        ...


class ManualProvider(EvalProvider):
    """Placeholder provider that returns fixed scores for all dimensions.

    Used as the default when no LLM is configured. Returns all dimensions=3
    (total=12), which maps to gate=ACCEPT. This ensures the pipeline works
    offline without any cloud API keys.
    """

    @property
    def name(self) -> str:
        return "manual"

    def score(self, doc: EvalDocument, prompt: str) -> str:
        """Return a hardcoded placeholder scoring response (all dims=3, total=12)."""
        payload = {
            "relevance": {"score": 3, "rationale": "Manual placeholder — human review required."},
            "novelty": {"score": 3, "rationale": "Manual placeholder — human review required."},
            "actionability": {"score": 3, "rationale": "Manual placeholder — human review required."},
            "credibility": {"score": 3, "rationale": "Manual placeholder — human review required."},
            "total": 12,
            "epistemic_type": "UNKNOWN",
            "summary": "Manual placeholder — human review required.",
            "key_findings": [],
            "eval_model": "manual_placeholder",
        }
        return json.dumps(payload)


class OllamaProvider(EvalProvider):
    """Ollama local LLM provider.

    Sends a scoring request to a local Ollama instance.
    Uses urllib.request (stdlib only — no requests dependency).
    """

    def __init__(self, model: str = "qwen3:30b", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    def score(self, doc: EvalDocument, prompt: str) -> str:
        """Score a document using Ollama.

        Raises:
            ConnectionError: If the Ollama endpoint is unreachable.
        """
        endpoint = f"{self._base_url}/api/generate"
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                return data.get("response", "{}")
        except Exception as exc:
            raise ConnectionError(f"Ollama endpoint unreachable at {endpoint}: {exc}") from exc


def get_provider(name: str = "manual", **kwargs) -> EvalProvider:
    """Factory function to get an evaluation provider by name.

    Supported providers:
    - "manual"  — ManualProvider (no LLM, placeholder scores)
    - "ollama"  — OllamaProvider (local Ollama LLM)

    Cloud providers (gemini, deepseek) deferred to RIS v2. See RIS_03_EVALUATION_GATE.md.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    if name == "manual":
        return ManualProvider()
    elif name == "ollama":
        return OllamaProvider(**kwargs)
    else:
        raise ValueError(
            f"unknown provider '{name}'. Supported: manual, ollama. "
            "Cloud providers (gemini, deepseek) are deferred to RIS v2."
        )
