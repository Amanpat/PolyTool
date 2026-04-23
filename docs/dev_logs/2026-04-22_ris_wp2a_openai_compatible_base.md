# WP2-A: OpenAI-Compatible Base Provider

**Date:** 2026-04-22
**Work packet:** WP2-A (RIS Phase 2A — Cloud Provider Infrastructure)
**Status:** COMPLETE

## Objective

Add a reusable `OpenAICompatibleProvider` base class to `packages/research/evaluation/providers.py` so that concrete cloud provider subclasses (DeepSeek, OpenRouter, Groq — WP2-C/D/E) have a shared foundation for request construction, JSON extraction, post-validation, and retry/backoff logic.

## What was built

### `packages/research/evaluation/providers.py`

**New internal exception hierarchy:**
- `_RetryableError(message, retry_after=0.0)` — raised on 429/502/503/timeout; `retry_after` carries the server-specified wait if present.
- `_NonRetryableError(message)` — raised on 400/403/malformed response; triggers immediate surface to caller.

**New class: `OpenAICompatibleProvider(EvalProvider)`**

- `_PROVIDER_NAME = "openai_compatible"` class variable; subclasses override to register their name (e.g., `_PROVIDER_NAME = "deepseek"`).
- Constructor: `api_key`, `base_url`, `model`, `max_retries=3`, `timeout=60`.
- `score(doc, prompt)` → calls `_call_with_retry(prompt)`.
- `_call_with_retry(prompt)` — exponential backoff (1s → 2s → 4s, capped at 30s), up to `max_retries` attempts. Surfaces `_NonRetryableError` immediately (no retry). Raises `ConnectionError` on exhausted retries, `PermissionError` for 403, `ValueError` for other 4xx.
- `_make_request(prompt)` — `urllib.request` POST to `{base_url}/chat/completions` with Bearer auth and `response_format: json_object`. Maps HTTP status codes to retryable/non-retryable exceptions. Handles `Retry-After` header and `retryDelay` body field on 429.
- `_validate_and_extract(raw_body)` — parses outer OpenAI envelope, extracts `choices[0].message.content`, falls back to `_try_extract_json()` for markdown-wrapped responses, runs `_post_validate()`.
- `_try_extract_json(text)` — static; regex extracts JSON from ` ```json ... ``` ` or ` ``` ... ``` ` code blocks.
- `_post_validate(payload)` — static; validates all four required dims, normalizes float scores to int, enforces 1-5 range. Mutates in place.

**Updated: `get_provider_metadata()`**

Switched from `isinstance(provider, ManualProvider)` / `isinstance(provider, OllamaProvider)` to duck-typing: checks `hasattr(provider, "model_id") and hasattr(provider, "generation_params")`. This handles ManualProvider, OllamaProvider, OpenAICompatibleProvider subclasses, and any future providers without requiring changes to this function.

## Design decisions

**stdlib only (no `openai` package dependency):** The roadmap said "Uses `openai` Python package," but the existing OllamaProvider uses `urllib.request` to avoid hard deps. Consistent with that pattern and avoids adding a dependency for what is ultimately a straightforward POST + JSON parse.

**Internal exception hierarchy, not public API:** `_RetryableError` / `_NonRetryableError` are prefixed with `_` and listed in the docstring as internal. The public error surface is `ConnectionError` (retries exhausted), `ValueError` (non-retryable 4xx), `PermissionError` (403). DocumentEvaluator's fail-closed `except Exception` handler wraps all of these.

**`get_provider()` factory unchanged for cloud names:** `gemini`, `deepseek`, `openai`, `anthropic` remain in `_CLOUD_PROVIDERS` and still raise `ValueError` even with the env var set. Concrete subclasses (WP2-C/D/E) will be wired into the factory at that point, removing the name from the "not yet implemented" path. The existing guard test `test_cloud_provider_env_var_set_but_not_implemented` passes unchanged.

## Tests

**File:** `tests/test_ris_wp2a_openai_compatible_base.py` — 41 tests, all passing.

Coverage:
- Properties: `name`, `model_id`, `generation_params`, subclass `_PROVIDER_NAME` override.
- `get_provider_metadata()` duck-typing: ManualProvider, OllamaProvider, OpenAICompatibleProvider, subclass, minimal provider without attrs.
- Successful path: valid envelope, float→int normalization, flat int dim format.
- Markdown fallback: `_try_extract_json` unit tests + end-to-end through `score()`.
- `_post_validate` unit tests: missing dim, missing score key, out-of-range, non-numeric, float normalization.
- `_validate_and_extract` unit tests: malformed outer JSON, missing choices, empty choices list, non-string content, invalid inner JSON, post-validate failure.
- Retry: 429/502/503 trigger retries; 400/403 do not; URL error triggers retry; retry succeeds on second attempt; `Retry-After` header respected.
- Regression: ManualProvider and OllamaProvider unchanged.

## Test run

```
tests/test_ris_wp2a_openai_compatible_base.py: 41 passed
Full suite: 2332 passed, 1 pre-existing failure (test_ris_claim_extraction.py::test_each_claim_has_required_fields — actor field changed from heuristic_v1 to heuristic_v2_nofrontmatter in commit 2d926c6, unrelated to WP2-A)
```

## Codex review

Tier: Recommended (strategy-adjacent provider code, no execution path).
Review: Not run — WP2-A adds no execution-layer code and the provider is not yet wired to a concrete cloud key. Recommend running before first real API call is hooked up in WP2-C/D/E.

## Open questions / next steps

- **WP2-C:** DeepSeek subclass — `DeepSeekProvider(_PROVIDER_NAME="deepseek", base_url="https://api.deepseek.com", model="deepseek-chat")`. Wire into `get_provider()` factory.
- **WP2-D:** OpenRouter subclass — `base_url="https://openrouter.ai/api/v1"`.
- **WP2-E:** Groq subclass — `base_url="https://api.groq.com/openai/v1"`.
- **Stale test:** `test_ris_claim_extraction.py::test_each_claim_has_required_fields` expects `actor == "heuristic_v1"` but the extractor now returns `"heuristic_v2_nofrontmatter"`. Needs a one-line fix to the test assertion — not blocking WP2-A.
