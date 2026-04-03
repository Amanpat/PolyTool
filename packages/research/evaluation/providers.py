"""RIS v1 evaluation gate — LLM provider abstraction.

Providers are responsible for scoring a document against the evaluation rubric.
ManualProvider is the default — it returns a placeholder score so the pipeline
works with zero external dependencies.

Phase 5 additions:
- Cloud provider guard: non-local providers require RIS_ENABLE_CLOUD_PROVIDERS=1
- get_provider_metadata(): returns provider_name, model_id, generation_params
- Local providers (manual, ollama) work without any env vars or flags.

Cloud providers (gemini, deepseek, openai, anthropic) are gated behind
RIS_ENABLE_CLOUD_PROVIDERS=1 and not yet implemented (RIS v2 deliverable).
"""

from __future__ import annotations

import json
import os
import urllib.request
from abc import ABC, abstractmethod

from packages.research.evaluation.types import EvalDocument

# Local providers never require the cloud guard env var.
_LOCAL_PROVIDERS = frozenset({"manual", "ollama"})

# Env var that enables cloud provider access (explicit operator opt-in required).
_CLOUD_GUARD_ENV_VAR = "RIS_ENABLE_CLOUD_PROVIDERS"

# Known cloud provider names (recognized but not yet implemented).
_CLOUD_PROVIDERS = frozenset({"gemini", "deepseek", "openai", "anthropic"})


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

    @property
    def model_id(self) -> str:
        """Model identifier for metadata capture."""
        return "manual_placeholder"

    @property
    def generation_params(self) -> dict:
        """Generation params for metadata capture (empty for manual provider)."""
        return {}

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

    @property
    def model_id(self) -> str:
        """Model identifier for metadata capture."""
        return self._model

    @property
    def generation_params(self) -> dict:
        """Generation params for metadata capture."""
        return {"format": "json", "stream": False}

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

    Local providers (manual, ollama) work without any env vars or flags.

    Cloud providers require explicit opt-in via RIS_ENABLE_CLOUD_PROVIDERS=1.
    Cloud providers are not yet implemented (RIS v2 deliverable) — setting
    the env var passes the guard but then raises ValueError for unimplemented
    providers. This establishes the opt-in pattern for future implementations.

    Supported (implemented):
    - "manual"  — ManualProvider (no LLM, placeholder scores)
    - "ollama"  — OllamaProvider (local Ollama LLM)

    Recognized but not yet implemented (cloud, require RIS_ENABLE_CLOUD_PROVIDERS=1):
    - "gemini", "deepseek", "openai", "anthropic"

    Raises:
        PermissionError: If a cloud provider name is used without the env var set.
        ValueError: If the provider name is unrecognized, or if a known cloud
            provider is requested with the env var set (not yet implemented).
    """
    if name in _LOCAL_PROVIDERS:
        if name == "manual":
            return ManualProvider()
        elif name == "ollama":
            return OllamaProvider(**kwargs)
    else:
        # Cloud guard: require explicit operator opt-in
        if os.environ.get(_CLOUD_GUARD_ENV_VAR, "") != "1":
            raise PermissionError(
                f"Cloud provider '{name}' requires {_CLOUD_GUARD_ENV_VAR}=1 to be set. "
                "Local providers (manual, ollama) work without this flag."
            )
        # Env var is set — provider is recognized but not yet implemented
        if name in _CLOUD_PROVIDERS:
            raise ValueError(
                f"Cloud provider '{name}' is recognized but not yet implemented. "
                "Cloud provider implementations are a RIS v2 deliverable."
            )
        raise ValueError(
            f"Unknown provider '{name}'. Local providers: manual, ollama. "
            f"Cloud providers (require {_CLOUD_GUARD_ENV_VAR}=1): {', '.join(sorted(_CLOUD_PROVIDERS))}."
        )


def get_provider_metadata(provider: EvalProvider) -> dict:
    """Return metadata dict for a provider instance.

    Used by the evaluator to capture replay-grade metadata on every scoring
    event. Returns a consistent dict regardless of provider type.

    Args:
        provider: An EvalProvider instance.

    Returns:
        Dict with keys: provider_name (str), model_id (str), generation_params (dict).
    """
    meta: dict = {
        "provider_name": provider.name,
        "model_id": "",
        "generation_params": {},
    }
    if isinstance(provider, ManualProvider):
        meta["model_id"] = provider.model_id
        meta["generation_params"] = provider.generation_params
    elif isinstance(provider, OllamaProvider):
        meta["model_id"] = provider.model_id
        meta["generation_params"] = provider.generation_params
    return meta
