# WP2-C: DeepSeek V3 Provider

**Date:** 2026-04-22
**Work packet:** WP2-C (RIS Phase 2A — Cloud Provider Infrastructure)
**Status:** COMPLETE

## Objective

Add a thin `DeepSeekV3Provider` subclass of `OpenAICompatibleProvider` with correct
DeepSeek V3 defaults, wire `"deepseek"` into `get_provider()` so it constructs the
provider when `RIS_ENABLE_CLOUD_PROVIDERS=1` is set, and add fail-fast env-var handling
for `DEEPSEEK_API_KEY`.

## What was built

### `packages/research/evaluation/providers.py`

**New class: `DeepSeekV3Provider(OpenAICompatibleProvider)`**

- `_PROVIDER_NAME = "deepseek"` — picked up by inherited `.name` property.
- `_BASE_URL = "https://api.deepseek.com/v1"` — hardcoded default.
- `_ENV_KEY = "DEEPSEEK_API_KEY"` — env var name for credential resolution.
- Constructor: `api_key=None, model="deepseek-chat", max_retries=3, timeout=60`.
  - Resolves key: `api_key or os.environ.get("DEEPSEEK_API_KEY", "")`.
  - Raises `PermissionError` at construction time if resolved key is empty.
  - Calls `super().__init__(api_key=..., base_url=_BASE_URL, model=..., ...)`.
- No method overrides — all HTTP, retry/backoff, JSON extraction, and post-validation
  logic is inherited from `OpenAICompatibleProvider`.

**Updated: `get_provider()`**

Inside the `elif name in _CLOUD_PROVIDERS` branch (after the guard passes):

```python
if name == "deepseek":
    return DeepSeekV3Provider(**kwargs)
```

`"gemini"`, `"openai"`, `"anthropic"` still fall through to the existing `ValueError`
("recognized but not yet implemented"). The guard test for `"gemini"` in
`test_ris_phase5_provider_enablement.py` is unaffected.

**Updated: module docstring** — added WP2-C section describing the new class and
factory routing change.

## Design decisions

**Fail-fast at construction, not at call time:** `PermissionError` is raised in
`__init__` before any network calls. This surfaces credential problems immediately
when the CLI parses provider config, not on the first scoring attempt minutes later.

**`api_key` defaults to `None` (not required):** Lets the factory call
`DeepSeekV3Provider(**kwargs)` cleanly. The env-var fallback in `__init__` covers
the common case where the key is in `.env`.

**Base URL includes `/v1` path segment:** DeepSeek's OpenAI-compatible endpoint is
`https://api.deepseek.com/v1` (not bare `https://api.deepseek.com`). The base class
appends `/chat/completions` to `_base_url`, so the full endpoint resolves to
`https://api.deepseek.com/v1/chat/completions`.

**No routing/fallback/budget logic added:** WP2-C is strictly about the concrete
provider class and factory wiring. Provider chain routing is a separate concern (WP2-F
or later).

## Tests

**File:** `tests/test_ris_wp2c_deepseek_provider.py` — 31 tests, all passing.

Coverage:
- Construction: explicit key, default model (`deepseek-chat`), default base URL,
  custom model, custom `max_retries`, custom `timeout`.
- Credentials: env-var resolution, explicit key takes precedence over env, missing
  key raises `PermissionError`, empty env var raises `PermissionError`.
- Metadata: `.name`, `_PROVIDER_NAME`, `model_id`, `generation_params` keys,
  `get_provider_metadata()` duck-typing.
- Factory: `get_provider("deepseek")` returns `DeepSeekV3Provider`; no cloud guard
  raises `PermissionError`; guard set but missing API key raises `PermissionError`;
  kwargs forwarded to provider.
- Unimplemented cloud providers (`gemini`, `openai`, `anthropic`) still raise
  `ValueError` after guard passes.
- Local provider regression: `ManualProvider` and `OllamaProvider` unaffected;
  unknown name raises `ValueError`.
- Score delegation: `score()` hits `urlopen` via inherited path; endpoint is
  `api.deepseek.com/v1/chat/completions`; `Authorization: Bearer <key>` header sent.

## Test run

```
tests/test_ris_wp2c_deepseek_provider.py: 31 passed
Full suite: 2332 passed, 1 pre-existing failure (test_ris_claim_extraction.py::test_each_claim_has_required_fields — actor field heuristic_v1 → heuristic_v2_nofrontmatter, commit 2d926c6, unrelated to WP2-C)
```

## Codex review

Tier: Recommended (strategy-adjacent provider code, no execution path).
Review: Not run — WP2-C adds no execution-layer code and the provider is not yet
wired to a live budget/routing chain. Recommend running before first real API call
is hooked up in WP2-F (provider chain routing).

## Open questions / next steps

- **WP2-D:** OpenRouter subclass — `base_url="https://openrouter.ai/api/v1"`.
- **WP2-E:** Groq subclass — `base_url="https://api.groq.com/openai/v1"`.
- **WP2-F:** Provider chain routing — priority order, budget gate, fallback logic.
- **Stale test (pre-existing):** `test_ris_claim_extraction.py::test_each_claim_has_required_fields`
  expects `actor == "heuristic_v1"` but actual is `"heuristic_v2_nofrontmatter"`.
  One-line fix to the test assertion; not blocking WP2-C or WP2-D/E.
