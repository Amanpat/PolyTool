# WP2-B: GeminiFlashProvider

**Date:** 2026-04-22
**Work packet:** WP2-B (RIS Phase 2A — Cloud Provider Infrastructure)
**Status:** COMPLETE

## Objective

Add a `GeminiFlashProvider` class to `packages/research/evaluation/providers.py`, wire
`get_provider("gemini")` to construct it when `RIS_ENABLE_CLOUD_PROVIDERS=1` is set, add
targeted tests, update the two stale tests that expected gemini to be unimplemented, and
update the `list-providers` CLI output.

## What was built

### `packages/research/evaluation/providers.py`

**New class: `GeminiFlashProvider(EvalProvider)`**

- Directly subclasses `EvalProvider` — NOT `OpenAICompatibleProvider`.
  Gemini uses a fundamentally different API: `generateContent` (not `chat/completions`),
  API key in URL query param (`?key=`), not an Authorization header, different
  request/response envelope, and a safety-block finish reason to handle.
- `_PROVIDER_NAME = "gemini"`.
- `_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"` — hardcoded.
- `_ENV_KEY = "GEMINI_API_KEY"` — env var for credential resolution.
- `_RESPONSE_SCHEMA` — class-level constrained decoding schema matching the four
  required evaluation dimensions. Passed as `responseSchema` in `generationConfig`,
  which constrains token sampling at the logit level for ~99.9% schema conformance.
- Constructor: `api_key=None, model="gemini-2.5-flash-preview-04-17", max_retries=3,
  timeout=60, min_request_interval=5.0`.
  - Resolves key: `api_key or os.environ.get("GEMINI_API_KEY", "")`.
  - Raises `PermissionError` at construction time if resolved key is empty.
  - Tracks `_last_request_time` (float, monotonic) for rate limiting.
- `score(doc, prompt)` → `_call_with_retry(prompt)`.
- `_call_with_retry(prompt)` — exponential backoff (1s → 2s → 4s, capped 30s), up to
  `max_retries` attempts. Non-retryable 403 surfaces as `PermissionError`; other
  non-retryable errors surface as `ValueError`. Retry exhaustion raises `ConnectionError`.
- `_make_request(prompt)` — rate-limit pacing via `time.monotonic()` diff; `urllib.request`
  POST to `{_BASE_URL}/{model}:generateContent?key={api_key}` with `responseMimeType` and
  `responseSchema` in `generationConfig`. 429 parses `error.details[].retryDelay` (format:
  `"30s"`). 503 is retryable; 400/403 are non-retryable. URLError/TimeoutError retryable.
- `_validate_and_extract(raw_body)` — parses Gemini response envelope
  `candidates[0].content.parts[0].text`. `finishReason == "SAFETY"` → non-retryable error
  (never retry safety-blocked prompts). Calls `OpenAICompatibleProvider._post_validate()`
  for shared score range/type validation (reuses existing static method, no duplication).
- **Updated: module docstring** — added WP2-B section.

**Updated: `get_provider()`**

Added `if name == "gemini": return GeminiFlashProvider(**kwargs)` inside the cloud-guard
branch, after the deepseek routing. Updated the docstring to reflect gemini as implemented.

### `tests/test_ris_wp2b_gemini_provider.py`

New file, 44 tests, all passing.

Coverage:
- Construction: explicit key, default model, custom model, default/custom max_retries,
  default/custom timeout, default/custom min_request_interval.
- Credentials: env-var resolution, explicit key takes precedence, missing key raises
  PermissionError, empty env var raises PermissionError.
- Metadata: `.name`, `_PROVIDER_NAME`, `model_id`, `generation_params` keys,
  `response_mime_type` value, `get_provider_metadata()` duck-typing.
- Factory: `get_provider("gemini")` returns `GeminiFlashProvider`; no cloud guard raises
  PermissionError; guard set but missing API key raises PermissionError; kwargs forwarded.
- Unimplemented cloud providers (`openai`, `anthropic`) still raise ValueError after guard.
- Local provider regression: `ManualProvider` and `OllamaProvider` unaffected; unknown
  name raises ValueError.
- Score delegation: round-trip through `_validate_and_extract`; endpoint contains
  `generateContent`; API key in URL query param, not Authorization header; model in URL.
- Safety block: `finishReason == "SAFETY"` raises ValueError.
- Empty candidates / missing content path raise ValueError.
- Out-of-range score raises ValueError (post_validate called).
- HTTP errors: 429 triggers retry and succeeds on second attempt; 429 with `retryDelay`
  parses "30s" correctly; 503 triggers retry; 400 raises ValueError immediately (no retry);
  403 raises PermissionError immediately (no retry); URLError exhaustion raises
  ConnectionError.

### Stale test updates

**`tests/test_ris_phase5_provider_enablement.py`**

`test_cloud_provider_env_var_set_but_not_implemented` was calling `get_provider("gemini")`
and expecting `ValueError("not yet implemented")`. After WP2-B, gemini is implemented —
calling it without `GEMINI_API_KEY` raises `PermissionError`, not `ValueError`. Updated
to use `get_provider("openai")` which remains unimplemented.

**`tests/test_ris_wp2c_deepseek_provider.py`**

`TestUnimplementedCloudProvidersUnchanged::test_gemini_still_raises_value_error` updated
to `test_gemini_raises_permission_error_without_api_key`. With cloud guard set but
`GEMINI_API_KEY` absent, `get_provider("gemini")` now raises `PermissionError` (not
`ValueError`). Test asserts `PermissionError` with "GEMINI_API_KEY" in the message.

### `tools/cli/research_eval.py`

`_cmd_list_providers` updated: gemini and deepseek lines now show their required API key
env vars (`GEMINI_API_KEY`, `DEEPSEEK_API_KEY`) instead of "(not yet implemented)".

## Design decisions

**Does NOT subclass `OpenAICompatibleProvider`:** Gemini's API is structurally different —
`generateContent` endpoint, key in URL query param (not Bearer header), different
request/response envelope, safety block finish reason. A subclass would require overriding
every method that matters, which is worse than a clean direct subclass of `EvalProvider`.

**Reuses `OpenAICompatibleProvider._post_validate()` as a static call:** The score
validation logic (required dims, float→int normalization, 1-5 range) is identical across
all providers. Called as `OpenAICompatibleProvider._post_validate(payload)` directly —
no duplication, no inheritance required.

**Constrained decoding via responseSchema:** `responseMimeType="application/json"` +
`responseSchema={...}` constrains token sampling at the logit level. This gives ~99.9%
schema conformance without needing a markdown code-block fallback like
`OpenAICompatibleProvider._try_extract_json`. If Gemini returns non-JSON despite this
(unexpected), `_validate_and_extract` raises a non-retryable error.

**Rate limiting via `min_request_interval`:** Default 5.0s (~12 RPM) stays below the
free-tier 15 RPM ceiling. Tests pass `min_request_interval=0.0` to skip rate-limit sleeps.
`time.sleep` is also patchable for tests that exercise the 429 path.

**`retryDelay` format:** Gemini's 429 body has `error.details[].retryDelay` as a string
like `"30s"`. Parsing strips the "s" suffix and converts to float. Failures in this parse
silently fall back to the exponential backoff delay.

**Safety block as non-retryable:** `finishReason == "SAFETY"` is never transient — the
same prompt will always be blocked. Raising `_NonRetryableError` immediately surfaces as
`ValueError` without burning retry budget.

**Model default `gemini-2.5-flash-preview-04-17`:** Matches the specific preview version
called out in the roadmap's "gemini-2.5-flash" guidance. Fully overridable via `model=`
kwarg.

## Tests

```
tests/test_ris_wp2b_gemini_provider.py: 44 passed
tests/test_ris_wp2c_deepseek_provider.py: 31 passed (test_gemini_still_raises_value_error → test_gemini_raises_permission_error_without_api_key)
tests/test_ris_phase5_provider_enablement.py: 20 passed (test_cloud_provider_env_var_set_but_not_implemented updated to use "openai")
tests/test_ris_wp2a_openai_compatible_base.py: 46 passed

Targeted suite (141 tests): 141 passed in 4.70s

Full suite: 4334 passed, 11 pre-existing failures
  - test_ris_claim_extraction.py (3): heuristic_v2_nofrontmatter actor mismatch, pre-existing since commit 2d926c6
  - test_ris_phase2_cloud_provider_routing.py (8): references providers._post_json and ProviderUnavailableError
    which are WP2-F routing infrastructure not yet built; pre-existing before WP2-B
```

## Codex review

Tier: Recommended (strategy-adjacent provider code, no execution path).
Review: Not run — WP2-B adds no execution-layer code and the provider is not yet wired
to a live budget/routing chain. Recommend running before first real API call is hooked
up in WP2-F (provider chain routing).

## Open questions / next steps

- **WP2-D:** OpenRouter subclass — `base_url="https://openrouter.ai/api/v1"`, subclasses
  `OpenAICompatibleProvider`.
- **WP2-E:** Groq subclass — `base_url="https://api.groq.com/openai/v1"`, subclasses
  `OpenAICompatibleProvider`.
- **WP2-F:** Provider chain routing — priority order, budget gate, fallback logic.
  `test_ris_phase2_cloud_provider_routing.py` contains the spec tests for this layer
  (currently 8 pre-existing failures).
- **Stale test (pre-existing):** `test_ris_claim_extraction.py` expects
  `actor == "heuristic_v1"` but actual is `"heuristic_v2_nofrontmatter"` since commit
  2d926c6. One-line fix; not blocking WP2-B.
