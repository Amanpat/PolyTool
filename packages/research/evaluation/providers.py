"""RIS v1 evaluation gate — LLM provider abstraction.

Providers are responsible for scoring a document against the evaluation rubric.
ManualProvider is the default — it returns a placeholder score so the pipeline
works with zero external dependencies.

Phase 5 additions:
- Cloud provider guard: non-local providers require RIS_ENABLE_CLOUD_PROVIDERS=1
- get_provider_metadata(): returns provider_name, model_id, generation_params
- Local providers (manual, ollama) work without any env vars or flags.

WP2-A additions:
- OpenAICompatibleProvider: reusable base for chat-completions style APIs.
  Concrete subclasses (DeepSeek, OpenRouter, Groq) come in WP2-C/D/E.
- _RetryableError / _NonRetryableError: internal exception hierarchy for the
  retry loop. Not part of the public API.
- get_provider_metadata() switched to duck-typing so future subclasses work
  automatically without isinstance updates.

WP2-B additions:
- GeminiFlashProvider: native Gemini generateContent provider with constrained
  JSON decoding via responseMimeType + responseSchema. Reads GEMINI_API_KEY from
  env; raises PermissionError if absent. Rate-limited to 12 RPM by default.
  Does NOT subclass OpenAICompatibleProvider — Gemini uses a different API
  structure (generateContent, not chat/completions; key in URL, not header).
- get_provider() now routes "gemini" to GeminiFlashProvider when
  RIS_ENABLE_CLOUD_PROVIDERS=1 is set.

WP2-C additions:
- DeepSeekV3Provider: thin OpenAICompatibleProvider subclass for DeepSeek V3.
  base_url="https://api.deepseek.com/v1", model="deepseek-chat".
  Reads DEEPSEEK_API_KEY from env; raises PermissionError if absent.
- get_provider() now routes "deepseek" to DeepSeekV3Provider when
  RIS_ENABLE_CLOUD_PROVIDERS=1 is set.

Cloud providers (gemini, deepseek, openai, anthropic) are gated behind
RIS_ENABLE_CLOUD_PROVIDERS=1. Gemini and DeepSeek are now implemented;
OpenRouter/Groq will be added as OpenAICompatibleProvider subclasses in WP2-D/E.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from packages.research.evaluation.types import EvalDocument

# Local providers never require the cloud guard env var.
_LOCAL_PROVIDERS = frozenset({"manual", "ollama"})

# Env var that enables cloud provider access (explicit operator opt-in required).
_CLOUD_GUARD_ENV_VAR = "RIS_ENABLE_CLOUD_PROVIDERS"

# Known cloud provider names (recognized but not yet implemented via factory).
_CLOUD_PROVIDERS = frozenset({"gemini", "deepseek", "openai", "anthropic"})


# ---------------------------------------------------------------------------
# Internal exception hierarchy (not part of the public API)
# ---------------------------------------------------------------------------

class _RetryableError(Exception):
    """Raised when the HTTP request failed with a retryable condition (429/502/503/timeout)."""

    def __init__(self, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class _NonRetryableError(Exception):
    """Raised when the HTTP request failed with a non-retryable condition (400/403/bad response)."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Local providers (no cloud guard required)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cloud base provider (WP2-A)
# ---------------------------------------------------------------------------

class OpenAICompatibleProvider(EvalProvider):
    """Reusable base class for OpenAI chat-completions compatible cloud providers.

    Handles the full scoring call lifecycle:
    - Request construction: POST to {base_url}/chat/completions with Bearer auth
      and response_format=json_object.
    - Retry/backoff: exponential backoff on 429/502/503/timeout (up to max_retries).
    - JSON extraction: direct parse + markdown code-block fallback.
    - Strict post-validation: required dims, float→int normalization, 1-5 range.
    - Clear error surfaces: ConnectionError after exhausted retries (retryable),
      ValueError for bad-request responses (non-retryable), PermissionError for 403.

    Subclasses set _PROVIDER_NAME and typically override __init__ to supply
    a known base_url and default model. All HTTP and validation logic lives here.

    Requires RIS_ENABLE_CLOUD_PROVIDERS=1 — enforced by get_provider() for
    named providers. Subclasses instantiated directly bypass the factory guard
    and must enforce the env var check themselves if needed.

    Args:
        api_key: Bearer token for the provider's API.
        base_url: Root URL for the provider's OpenAI-compatible endpoint.
        model: Model identifier string (e.g. "deepseek-chat").
        max_retries: Maximum retry attempts on retryable errors (default 3).
        timeout: HTTP request timeout in seconds (default 60).
    """

    _PROVIDER_NAME: str = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
        timeout: int = 60,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max_retries
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._PROVIDER_NAME

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def generation_params(self) -> dict:
        return {
            "temperature": 0.1,
            "max_tokens": 1500,
            "response_format": "json_object",
        }

    def score(self, doc: EvalDocument, prompt: str) -> str:
        """Score a document via the OpenAI-compatible endpoint.

        Raises:
            ConnectionError: If the request fails after all retries are exhausted.
            ValueError: If the provider returns a non-retryable 4xx error.
            PermissionError: If the provider returns HTTP 403.
        """
        return self._call_with_retry(prompt)

    def _call_with_retry(self, prompt: str) -> str:
        """Call the endpoint with exponential backoff on retryable failures."""
        last_exc: Exception = RuntimeError("no attempts made")
        delay = 1.0
        for attempt in range(self._max_retries):
            try:
                return self._make_request(prompt)
            except _RetryableError as exc:
                last_exc = exc
                wait = exc.retry_after if exc.retry_after > 0 else delay
                time.sleep(min(wait, 30.0))
                delay = min(delay * 2, 30.0)
            except _NonRetryableError as exc:
                # Surface non-retryable errors immediately without further attempts
                msg = str(exc)
                if "403" in msg or "Forbidden" in msg:
                    raise PermissionError(msg) from exc
                raise ValueError(msg) from exc
        raise ConnectionError(
            f"Provider '{self.name}' failed after {self._max_retries} attempts: {last_exc}"
        ) from last_exc

    def _make_request(self, prompt: str) -> str:
        """Make a single HTTP POST to the chat completions endpoint.

        Returns:
            Validated inner JSON string ready for parse_scoring_response().

        Raises:
            _RetryableError: On HTTP 429/502/503 or network/timeout error.
            _NonRetryableError: On HTTP 400/403 or malformed response structure.
        """
        endpoint = f"{self._base_url}/chat/completions"
        body = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1500,
        }).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                return self._validate_and_extract(raw)
        except urllib.error.HTTPError as exc:
            status = exc.code
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if status == 429:
                retry_after = 0.0
                try:
                    retry_after = float(exc.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    pass
                if not retry_after:
                    try:
                        retry_data = json.loads(body_text)
                        retry_after = float(retry_data.get("retryDelay") or 0)
                    except Exception:
                        pass
                raise _RetryableError(
                    f"Rate limited (429): {body_text[:200]}", retry_after=retry_after
                )
            elif status in (502, 503):
                raise _RetryableError(f"Service unavailable ({status}): {body_text[:200]}")
            elif status == 403:
                raise _NonRetryableError(f"Forbidden (403): {body_text[:200]}")
            elif status == 400:
                raise _NonRetryableError(f"Bad request (400): {body_text[:200]}")
            else:
                raise _NonRetryableError(f"HTTP {status}: {body_text[:200]}")
        except urllib.error.URLError as exc:
            raise _RetryableError(f"URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise _RetryableError(f"Request timeout after {self._timeout}s") from exc

    def _validate_and_extract(self, raw_body: str) -> str:
        """Parse the outer OpenAI response envelope and return validated inner JSON.

        Raises:
            _NonRetryableError: On malformed response structure or invalid content.
        """
        try:
            outer = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise _NonRetryableError(f"Outer response is not valid JSON: {exc}") from exc

        try:
            content = outer["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _NonRetryableError(
                f"Response missing choices[0].message.content: {exc}"
            ) from exc

        if not isinstance(content, str):
            raise _NonRetryableError(f"content is not a string: {type(content)}")

        # Direct parse; fall back to markdown code-block extraction
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            extracted = self._try_extract_json(content)
            if extracted is None:
                raise _NonRetryableError(
                    f"Inner content is not valid JSON and no code block found: {content[:200]}"
                )
            try:
                payload = json.loads(extracted)
            except json.JSONDecodeError as exc:
                raise _NonRetryableError(f"Extracted JSON is invalid: {exc}") from exc

        self._post_validate(payload)
        return json.dumps(payload)

    @staticmethod
    def _try_extract_json(text: str) -> str | None:
        """Extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)."""
        for pattern in (r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"):
            m = re.search(pattern, text, re.DOTALL)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _post_validate(payload: dict) -> None:
        """Validate and normalize scoring dimensions in place.

        Normalizes float scores to int. Validates 1-5 range. Does not check
        optional fields (total, summary, etc.) — parse_scoring_response handles those.

        Raises:
            _NonRetryableError: If required dims are missing, score is non-numeric,
                or score is outside [1, 5] after normalization.
        """
        required_dims = ("relevance", "novelty", "actionability", "credibility")
        for dim in required_dims:
            if dim not in payload:
                raise _NonRetryableError(f"Missing required dimension '{dim}' in response")
            entry = payload[dim]
            if isinstance(entry, dict):
                raw_score = entry.get("score")
                if raw_score is None:
                    raise _NonRetryableError(f"Missing 'score' key in dimension '{dim}'")
                try:
                    score = int(float(raw_score))
                except (TypeError, ValueError) as exc:
                    raise _NonRetryableError(
                        f"Non-numeric score for '{dim}': {raw_score!r}"
                    ) from exc
                if not 1 <= score <= 5:
                    raise _NonRetryableError(f"Score {score} out of range [1,5] for '{dim}'")
                entry["score"] = score  # normalize float -> int in place
            elif isinstance(entry, (int, float)):
                score = int(float(entry))
                if not 1 <= score <= 5:
                    raise _NonRetryableError(f"Score {score} out of range [1,5] for '{dim}'")
                payload[dim] = score
            else:
                raise _NonRetryableError(
                    f"Unexpected type for '{dim}': {type(entry).__name__}"
                )


# ---------------------------------------------------------------------------
# Cloud concrete providers (WP2-C+)
# ---------------------------------------------------------------------------

class DeepSeekV3Provider(OpenAICompatibleProvider):
    """DeepSeek V3 provider (deepseek-chat via OpenAI-compatible endpoint).

    Thin subclass of OpenAICompatibleProvider. All HTTP, retry, JSON extraction,
    and post-validation logic is inherited from the base.

    Reads DEEPSEEK_API_KEY from the environment. Raises PermissionError at
    construction time if the key is absent, so errors surface early before
    any network calls.

    Args:
        api_key: Bearer token. If None, reads DEEPSEEK_API_KEY from env.
        model: Model identifier (default "deepseek-chat").
        max_retries: Max retry attempts on retryable errors (default 3).
        timeout: HTTP timeout in seconds (default 60).
    """

    _PROVIDER_NAME = "deepseek"
    _BASE_URL = "https://api.deepseek.com/v1"
    _ENV_KEY = "DEEPSEEK_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        max_retries: int = 3,
        timeout: int = 60,
    ) -> None:
        resolved_key = api_key or os.environ.get(self._ENV_KEY, "")
        if not resolved_key:
            raise PermissionError(
                f"DeepSeekV3Provider requires {self._ENV_KEY} to be set in the environment."
            )
        super().__init__(
            api_key=resolved_key,
            base_url=self._BASE_URL,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
        )


class GeminiFlashProvider(EvalProvider):
    """Google Gemini Flash provider with constrained JSON decoding.

    Uses Gemini's native generateContent REST API — NOT the OpenAI-compatible
    endpoint. Constrained decoding via responseMimeType="application/json" +
    responseSchema pins token sampling at the logit level, giving ~99.9%
    schema conformance without post-hoc parsing heroics.

    Auth: API key passed as ?key= query param, not as a Bearer header.
    Rate limit: free tier allows 15 RPM. Default min_request_interval=5.0s
    (~12 RPM) stays below that ceiling.

    Reads GEMINI_API_KEY from the environment. Raises PermissionError at
    construction time if the key is absent.

    Args:
        api_key: API key. If None, reads GEMINI_API_KEY from env.
        model: Model identifier (default "gemini-2.5-flash-preview-04-17").
        max_retries: Max retry attempts on retryable errors (default 3).
        timeout: HTTP timeout in seconds (default 60).
        min_request_interval: Minimum seconds between requests for rate
            limiting (default 5.0, ~12 RPM).
    """

    _PROVIDER_NAME = "gemini"
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    _ENV_KEY = "GEMINI_API_KEY"

    _RESPONSE_SCHEMA: dict = {
        "type": "OBJECT",
        "properties": {
            "relevance": {
                "type": "OBJECT",
                "properties": {
                    "score": {"type": "INTEGER"},
                    "rationale": {"type": "STRING"},
                },
                "required": ["score", "rationale"],
            },
            "novelty": {
                "type": "OBJECT",
                "properties": {
                    "score": {"type": "INTEGER"},
                    "rationale": {"type": "STRING"},
                },
                "required": ["score", "rationale"],
            },
            "actionability": {
                "type": "OBJECT",
                "properties": {
                    "score": {"type": "INTEGER"},
                    "rationale": {"type": "STRING"},
                },
                "required": ["score", "rationale"],
            },
            "credibility": {
                "type": "OBJECT",
                "properties": {
                    "score": {"type": "INTEGER"},
                    "rationale": {"type": "STRING"},
                },
                "required": ["score", "rationale"],
            },
        },
        "required": ["relevance", "novelty", "actionability", "credibility"],
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash-preview-04-17",
        max_retries: int = 3,
        timeout: int = 60,
        min_request_interval: float = 5.0,
    ) -> None:
        resolved_key = api_key or os.environ.get(self._ENV_KEY, "")
        if not resolved_key:
            raise PermissionError(
                f"GeminiFlashProvider requires {self._ENV_KEY} to be set in the environment."
            )
        self._api_key = resolved_key
        self._model = model
        self._max_retries = max_retries
        self._timeout = timeout
        self._min_request_interval = min_request_interval
        self._last_request_time: float = 0.0

    @property
    def name(self) -> str:
        return self._PROVIDER_NAME

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def generation_params(self) -> dict:
        return {
            "temperature": 0.1,
            "max_output_tokens": 1500,
            "response_mime_type": "application/json",
            "response_schema": "constrained",
        }

    def score(self, doc: EvalDocument, prompt: str) -> str:
        return self._call_with_retry(prompt)

    def _call_with_retry(self, prompt: str) -> str:
        last_exc: Exception = RuntimeError("no attempts made")
        delay = 1.0
        for _attempt in range(self._max_retries):
            try:
                return self._make_request(prompt)
            except _RetryableError as exc:
                last_exc = exc
                wait = exc.retry_after if exc.retry_after > 0 else delay
                time.sleep(min(wait, 30.0))
                delay = min(delay * 2, 30.0)
            except _NonRetryableError as exc:
                msg = str(exc)
                if "403" in msg or "Forbidden" in msg:
                    raise PermissionError(msg) from exc
                raise ValueError(msg) from exc
        raise ConnectionError(
            f"Provider '{self.name}' failed after {self._max_retries} attempts: {last_exc}"
        ) from last_exc

    def _make_request(self, prompt: str) -> str:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        endpoint = (
            f"{self._BASE_URL}/{self._model}:generateContent?key={self._api_key}"
        )
        body = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self._RESPONSE_SCHEMA,
                "temperature": 0.1,
                "maxOutputTokens": 1500,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            self._last_request_time = time.monotonic()
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                return self._validate_and_extract(raw)
        except urllib.error.HTTPError as exc:
            status = exc.code
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if status == 429:
                retry_after = 0.0
                try:
                    err_data = json.loads(body_text)
                    for detail in err_data.get("error", {}).get("details", []):
                        if "retryDelay" in detail:
                            delay_str = str(detail["retryDelay"]).rstrip("s")
                            retry_after = float(delay_str)
                            break
                except Exception:
                    pass
                raise _RetryableError(
                    f"Rate limited (429): {body_text[:200]}", retry_after=retry_after
                )
            elif status == 503:
                raise _RetryableError(f"Service unavailable (503): {body_text[:200]}")
            elif status == 403:
                raise _NonRetryableError(f"Forbidden (403): {body_text[:200]}")
            elif status == 400:
                raise _NonRetryableError(f"Bad request (400): {body_text[:200]}")
            else:
                raise _NonRetryableError(f"HTTP {status}: {body_text[:200]}")
        except urllib.error.URLError as exc:
            raise _RetryableError(f"URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise _RetryableError(f"Request timeout after {self._timeout}s") from exc

    def _validate_and_extract(self, raw_body: str) -> str:
        try:
            outer = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise _NonRetryableError(f"Outer response is not valid JSON: {exc}") from exc

        candidates = outer.get("candidates", [])
        if not candidates:
            raise _NonRetryableError("Response has no candidates")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason == "SAFETY":
            raise _NonRetryableError(
                f"Gemini blocked response for safety reasons: {raw_body[:200]}"
            )

        try:
            content_text = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _NonRetryableError(
                f"Response missing candidates[0].content.parts[0].text: {exc}"
            ) from exc

        if not isinstance(content_text, str):
            raise _NonRetryableError(
                f"content text is not a string: {type(content_text)}"
            )

        try:
            payload = json.loads(content_text)
        except json.JSONDecodeError as exc:
            raise _NonRetryableError(
                f"Inner content is not valid JSON (unexpected with constrained decoding): {exc}"
            ) from exc

        OpenAICompatibleProvider._post_validate(payload)
        return json.dumps(payload)


# ---------------------------------------------------------------------------
# Factory and metadata helpers
# ---------------------------------------------------------------------------

def get_provider(name: str = "manual", **kwargs) -> EvalProvider:
    """Factory function to get an evaluation provider by name.

    Local providers (manual, ollama) work without any env vars or flags.

    Cloud providers require explicit opt-in via RIS_ENABLE_CLOUD_PROVIDERS=1.

    Supported (implemented):
    - "manual"   — ManualProvider (no LLM, placeholder scores)
    - "ollama"   — OllamaProvider (local Ollama LLM)
    - "deepseek" — DeepSeekV3Provider (requires RIS_ENABLE_CLOUD_PROVIDERS=1
                   and DEEPSEEK_API_KEY env vars)
    - "gemini"   — GeminiFlashProvider (requires RIS_ENABLE_CLOUD_PROVIDERS=1
                   and GEMINI_API_KEY env vars)

    Recognized but not yet implemented (cloud, require RIS_ENABLE_CLOUD_PROVIDERS=1):
    - "openai", "anthropic"

    Raises:
        PermissionError: If a cloud provider name is used without the env var set,
            or if the provider's API key env var is missing at construction time.
        ValueError: If the provider name is unrecognized, or if a known cloud
            provider is requested with the env var set but is not yet implemented.
    """
    if name in _LOCAL_PROVIDERS:
        if name == "manual":
            return ManualProvider()
        elif name == "ollama":
            return OllamaProvider(**kwargs)
    elif name in _CLOUD_PROVIDERS:
        # Known cloud provider: require explicit operator opt-in
        if os.environ.get(_CLOUD_GUARD_ENV_VAR, "") != "1":
            raise PermissionError(
                f"Cloud provider '{name}' requires {_CLOUD_GUARD_ENV_VAR}=1 to be set. "
                "Local providers (manual, ollama) work without this flag."
            )
        # Route implemented cloud providers
        if name == "deepseek":
            return DeepSeekV3Provider(**kwargs)
        if name == "gemini":
            return GeminiFlashProvider(**kwargs)
        # Env var is set but provider not yet implemented
        raise ValueError(
            f"Cloud provider '{name}' is recognized but not yet implemented. "
            "Cloud provider implementations are a RIS v2 deliverable."
        )
    else:
        # Completely unknown provider name
        raise ValueError(
            f"unknown provider '{name}'. Local providers: manual, ollama. "
            f"Cloud providers (require {_CLOUD_GUARD_ENV_VAR}=1): {', '.join(sorted(_CLOUD_PROVIDERS))}."
        )


def get_provider_metadata(provider: EvalProvider) -> dict:
    """Return metadata dict for a provider instance.

    Used by the evaluator to capture replay-grade metadata on every scoring
    event. Returns a consistent dict regardless of provider type.

    Duck-typed: any provider with model_id and generation_params attributes
    has those fields populated. This covers ManualProvider, OllamaProvider,
    OpenAICompatibleProvider subclasses, and future providers without needing
    isinstance updates.

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
    if hasattr(provider, "model_id") and hasattr(provider, "generation_params"):
        meta["model_id"] = provider.model_id
        meta["generation_params"] = provider.generation_params
    return meta
