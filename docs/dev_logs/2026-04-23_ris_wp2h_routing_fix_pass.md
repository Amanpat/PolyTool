# RIS WP2-H Routing Fix Pass

Date: 2026-04-23
Scope: Fix two blocking findings from WP2-H Codex verification
Status: COMPLETE

## Summary

Patched two blockers in the WP2-H multi-provider routing layer identified by the
`docs/dev_logs/2026-04-23_ris_wp2h_codex_verification.md` Codex verification report.
Added three new tests covering config-driven `evaluate_document()` activation and
escalation construction failure. All 11 routing tests pass. Full suite: 2332 pass, 1
pre-existing failure (unrelated, documented below).

## Blocker 1 — Config-driven routing not wired into evaluate_document()

**Root cause:** `evaluate_document()` had `provider_name: Optional[str] = None` in its
signature but always resolved it to `"manual"` before constructing `DocumentEvaluator`.
`routing_mode` was never passed to the evaluator, so setting
`RIS_EVAL_ROUTING_MODE=route` in JSON or env had no effect through the public API.

**Fix in `packages/research/evaluation/evaluator.py`:**
- Changed `provider_name` default from `"manual"` to `None`.
- When `provider_name is None`: reads `get_eval_config().routing` to select
  `primary_provider` (route mode) or `"manual"` (direct/default mode), and passes the
  resolved `routing_mode` to `DocumentEvaluator`.
- When `provider_name` is explicit: forces `routing_mode="direct"` — caller owns the
  provider, no escalation fires. Backward compatible.

**Fix in `tools/cli/research_eval.py`:**
- Changed `--provider` default from `"manual"` to `None`.
- Added effective-provider resolution block: when `--provider` is not given, reads
  routing config to determine the effective provider before the cloud guard check.
- Cloud guard is run against the effective provider (not a hardcoded "manual").
- `evaluate_document(..., provider_name=args.provider)` still passes `None` when
  `--provider` was not given, so the routing logic in `evaluate_document()` is the
  single source of truth for provider selection.

## Blocker 2 — Escalation provider construction not fail-closed

**Root cause:** `_score_with_routing()` called `self._get_escalation_provider()` before
`_call_provider_once()`. Any exception from construction (e.g., `PermissionError` from
missing `RIS_ENABLE_CLOUD_PROVIDERS`, `ValueError` from unknown provider name) propagated
uncaught — no REJECT artifact was written, and the exception reached the caller.

**Fix in `packages/research/evaluation/evaluator.py`:**
- Added `_ProviderStub` class (duck-types the provider interface: `.name`, `.model_id`,
  `.generation_params`) so `_build_provider_event()` can record a `ProviderEvent` for a
  failed escalation attempt without a real provider instance.
- Wrapped `_get_escalation_provider()` in `try/except/else`:
  - **except path:** constructs a fail-closed `ScoringResult(reject_reason="scorer_failure")`,
    appends `(_ProviderStub(esc_name), "", "")` to the calls list, sets `scores` to the
    failure result. Artifact records both primary attempt and failed escalation event.
  - **else path:** unchanged — calls escalation provider, records second event.

## New tests (3 added to test_ris_phase2_cloud_provider_routing.py)

1. `test_evaluate_document_route_mode_two_provider_events` — sets
   `RIS_EVAL_ROUTING_MODE=route`, `RIS_EVAL_PRIMARY_PROVIDER=manual`,
   `RIS_EVAL_ESCALATION_PROVIDER=manual`; calls `evaluate_document()` with no
   provider_name; asserts `gate == "REVIEW"` and `len(provider_events) == 2`.

2. `test_evaluate_document_explicit_provider_bypasses_route_mode` — same env vars
   (route mode); calls `evaluate_document(..., provider_name="manual")`; asserts
   `len(provider_events) == 1` (direct mode forced by explicit provider).

3. `test_escalation_construction_fails_closed_via_config` — route mode,
   primary=manual, escalation=deepseek, `RIS_ENABLE_CLOUD_PROVIDERS` unset; calls
   `evaluate_document()` without provider; asserts `gate == "REJECT"`,
   `reject_reason == "scorer_failure"`, `len(provider_events) == 2`,
   `events[0]["provider_name"] == "manual"`, `events[1]["provider_name"] == "deepseek"`.

## Test results

```
python -m pytest tests/test_ris_phase2_cloud_provider_routing.py -v --tb=short
11 passed in 0.21s

python -m pytest tests/ -x -q --tb=short
2332 passed, 1 failed (pre-existing), 3 deselected, 19 warnings in 63.75s
```

**Pre-existing failure (not caused by this patch):**
`tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields`
asserts `actor == "heuristic_v1"` but the extractor was renamed to
`heuristic_v2_nofrontmatter` in commit `2d926c6 feat(ris): strip YAML frontmatter in
heuristic claim extractor (v2)`. This is a test/implementation mismatch predating this
patch and is unrelated to routing.

## Files changed

- `packages/research/evaluation/evaluator.py` — `_ProviderStub` class, `_score_with_routing` fail-closed escalation, `evaluate_document` routing wiring
- `tools/cli/research_eval.py` — `--provider` default None, effective-provider resolution, cloud guard against effective provider
- `tests/test_ris_phase2_cloud_provider_routing.py` — 3 new tests (11 total, all pass)

## Codex review

Tier: Recommended (evaluation module).
Issues found: 2 blocking (addressed above).
Issues addressed: both blockers resolved; no new advisory issues introduced.
