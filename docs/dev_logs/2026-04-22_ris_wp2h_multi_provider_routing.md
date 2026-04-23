# WP2-H: Multi-Provider Routing

**Date:** 2026-04-22
**Work packet:** WP2-H (RIS Phase 2A — Config-Driven Multi-Provider Routing)
**Status:** COMPLETE

## Objective

Add config-driven multi-provider routing to the RIS evaluation gate.
Direct single-provider mode unchanged. Route mode escalates yellow-band
(REVIEW gate) results from the primary provider to a secondary provider.
Every scoring attempt is recorded in `provider_events` in order.

Scope: `evaluator.py`, `config.py`, `ris_eval_config.json`, routing tests,
dev log. No changes to providers, scoring, artifacts, or hard stops.

## What was built

### `packages/research/evaluation/evaluator.py`

**`DocumentEvaluator.__init__`** — two new optional parameters:

- `routing_mode: str = "direct"` — `"direct"` for single-provider (default),
  `"route"` to enable Gemini-primary / DeepSeek-escalation for REVIEW results.
- `escalation_provider: Optional[EvalProvider] = None` — explicit escalation
  provider for tests; constructed lazily from config if `None` and routing_mode
  is `"route"`.

**New private methods:**

- `_score_with_routing(doc)` → `(ScoringResult, List[Tuple[provider, raw, ph]])`:
  Calls `_call_provider_once`, applies priority tier, checks gate. Escalates
  only when `routing_mode == "route"` AND `scores.gate == "REVIEW"`. Appends
  escalation call to the call log for artifact capture. Returns final scores
  and full call log.

- `_call_provider_once(provider, doc)` → `(ScoringResult, raw_output, prompt_hash)`:
  Fail-closed. Any exception from `score_document_with_metadata` returns a
  `ScoringResult(reject_reason="scorer_failure")` with empty raw/hash instead
  of propagating. A failed primary never escalates (scorer_failure → REJECT,
  not REVIEW).

- `_apply_priority_tier(scores)` → `ScoringResult`:
  Must be called before checking `scores.gate` so the gate uses the correct
  threshold for the configured tier.

- `_build_provider_event(doc, provider, raw_output, prompt_hash, now)`:
  Builds one `ProviderEvent` per scoring attempt. `raw_output=None` in the
  persisted artifact (lightweight by default).

- `_get_escalation_provider()`:
  Returns `self._escalation_provider` if set; otherwise constructs from
  `get_eval_config().routing.escalation_provider`.

**`evaluate()` step 4 → 5 change:**

Step 4 now calls `_score_with_routing(doc)` instead of the old single-provider
path. Step 5 builds `provider_events` from the returned call log:
```python
provider_events = [
    dataclasses.asdict(self._build_provider_event(doc, p, raw, ph, now))
    for p, raw, ph in provider_calls
]
```
Direct mode always produces one entry. Route mode produces two entries when
escalation is triggered.

### `packages/research/evaluation/config.py`

**`RoutingConfig`** (new frozen dataclass):
```python
@dataclass(frozen=True)
class RoutingConfig:
    mode: str = "direct"
    primary_provider: str = "gemini"
    escalation_provider: str = "deepseek"
```

**`EvalConfig`** — new field:
```python
routing: RoutingConfig = field(default_factory=RoutingConfig)
```

**`load_eval_config()`** — new env-var overrides:
- `RIS_EVAL_ROUTING_MODE` (str, default: `direct`)
- `RIS_EVAL_PRIMARY_PROVIDER` (str, default: `gemini`)
- `RIS_EVAL_ESCALATION_PROVIDER` (str, default: `deepseek`)

Priority: env vars > `routing` section in JSON > hardcoded defaults.

### `config/ris_eval_config.json`

Added `routing` section:
```json
"routing": {
  "mode": "direct",
  "primary_provider": "gemini",
  "escalation_provider": "deepseek"
}
```

### `tests/test_ris_phase2_cloud_provider_routing.py` (full rewrite)

Previous file had 8 tests referencing stale private interfaces
(`providers._post_json`, `ProviderUnavailableError`, `decision.routing`,
`scores.eval_provider`, `cfg.routing.fallback_provider`) that were never
implemented. Replaced with 8 tests against the actual WP2-H API.

Tests use `_StaticProvider` duck-typed stub (name, model_id, generation_params
properties + score() method; optionally raises on score()).

Score algebra:
- `_payload(3,3,3,3,...)` → composite 3.0 < P3 threshold 3.2 → **REVIEW**
- `_payload(4,4,4,4,...)` → composite 4.0 ≥ 3.2 → **ACCEPT**

Test coverage:

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_routing_config_loads_from_json` | JSON routing section loads into RoutingConfig |
| 2 | `test_routing_config_env_overrides` | Env vars override JSON routing values |
| 3 | `test_direct_mode_primary_accepted` | Direct mode: ACCEPT returned, escalation not called |
| 4 | `test_direct_mode_primary_review_no_escalation` | Direct mode: REVIEW returned, escalation not called |
| 5 | `test_route_mode_primary_accepted_no_escalation` | Route mode: ACCEPT skips escalation |
| 6 | `test_route_mode_primary_review_escalates_and_accepts` | Route mode: REVIEW triggers escalation; artifact has 2 events in order |
| 7 | `test_route_mode_primary_exception_fails_closed` | Primary exception → REJECT scorer_failure, no escalation, 1 artifact event |
| 8 | `test_route_mode_escalation_exception_fails_closed` | Escalation exception → REJECT scorer_failure, 2 artifact events |

## Design decisions

**Escalation only on REVIEW, never on REJECT:** `scorer_failure` from a
primary exception produces `gate="REJECT"`, not `"REVIEW"`. The routing check
is `scores.gate == "REVIEW"` so a failed primary never escalates. This avoids
burning the escalation budget on documents that are definitively bad.

**`_apply_priority_tier` before gate check:** `ScoringResult.gate` is computed
lazily from `priority_tier` and `composite_score`. Priority tier must be set
before checking `scores.gate == "REVIEW"` or the wrong threshold is used.

**Call log as `List[Tuple[provider, raw, ph]]`:** Decouples routing logic from
artifact building. `_score_with_routing` returns the log; `evaluate()` builds
`ProviderEvent` objects only when `artifacts_dir` is set — no wasted work in
the no-artifact path.

**Lazy escalation provider construction:** `_get_escalation_provider()` only
calls `get_eval_config()` and `get_provider()` when escalation is actually
triggered. Tests that never reach the escalation path have zero config/provider
overhead.

## Tests

```
tests/test_ris_phase2_cloud_provider_routing.py: 8 passed
Broader RIS suite (evaluation + weighted_gate + provider_enablement + routing): 125 passed in 0.56s
```

## Codex review

Tier: Recommended (strategy-adjacent routing layer).
Review: Not run — WP2-H wires config to existing provider stubs but does not
touch execution, budget, or live API paths. Recommend running before first
live `routing_mode="route"` deployment.

## Open questions / next steps

- **WP2-D / WP2-E:** OpenRouter and Groq subclasses (OpenAICompatibleProvider
  subclasses). Would expand the set of named providers available to routing.
- **Live route mode activation:** Currently JSON has `"mode": "direct"`. Flip
  to `"route"` (or set `RIS_EVAL_ROUTING_MODE=route`) once Gemini and DeepSeek
  API keys are provisioned and the cloud guard is enabled.
- **Budget gate:** Routing does not check per-source or daily budgets yet.
  That is a Phase 2 budget sub-task.
