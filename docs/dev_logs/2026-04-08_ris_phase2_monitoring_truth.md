# Dev Log: RIS Phase 2 Monitoring Truth

**Date:** 2026-04-08
**Task:** quick-260408-oyu — Finish Phase 2 RIS monitoring truth
**Status:** Complete

## What Was Done

Turned Phase 2 RIS monitoring from "basic counts" into "operator-usable truth."
Previously, two health checks were stubs returning hardcoded GREEN. The metrics
snapshot also lacked routing, failure, queue, and disposition data.

### Changes

#### packages/research/metrics.py

Added 5 new fields to `RisMetricsSnapshot`:

- `provider_route_distribution` — count of evals per `selected_provider` from
  `routing_decision` in eval artifacts.
- `provider_failure_counts` — count of failures per `failure_reason` from
  `provider_events` in eval artifacts (only non-success events counted).
- `review_queue` — `queue_depth`, `by_status`, and `by_gate` from a read-only
  SQL query on `pending_review` table. Handles missing table gracefully
  (fresh DBs that have not run RIS yet).
- `disposition_distribution` — ACCEPT / REVIEW / REJECT / BLOCKED counts.
  BLOCKED = gate REJECT where `scores.reject_reason == "scorer_failure"`.
- `routing_summary` — `escalation_count`, `fallback_count`, `direct_count`,
  `total_routed` from `routing_decision.escalated` / `used_fallback` flags.

Updated `format_metrics_summary()` to display 4 new sections: Provider Routing,
Provider Failures, Review Queue, Dispositions.

#### packages/research/monitoring/health_checks.py

- Replaced `_check_model_unavailable()` stub with a real implementation:
  - GREEN when no failure data (no eval artifacts yet).
  - YELLOW when total failures > 3.
  - RED when all configured providers (from optional `routing_config`) have
    failures simultaneously.
  - Data dict no longer contains `deferred=True` or `check_type="stub"`.

- Added `_check_review_queue_backlog(review_queue)`:
  - GREEN when depth <= 20 or no data.
  - YELLOW when depth > 20.
  - RED when depth > 50.

- Updated `evaluate_health()` to accept `provider_failure_counts`,
  `review_queue`, and `routing_config` keyword args. Returns 7 results (was 6).

- Updated `ALL_CHECKS` registry to 7 entries with accurate descriptions.

#### tools/cli/research_health.py

- After loading runs, calls `collect_ris_metrics()` to get `provider_failure_counts`
  and `review_queue`, then passes them to `evaluate_health()`.
- Added `_determine_overall_category()` that maps check results to one of four
  operator-meaningful states: HEALTHY / DEGRADED / BLOCKED_ON_SETUP / FAILURE.
- `_output_table()` now prints `Overall: {category}` after the check table,
  with a setup hint for BLOCKED_ON_SETUP.
- `_output_json()` now includes `overall_category` field alongside `summary`.

#### docs/RIS_OPERATOR_GUIDE.md

- Updated health monitoring section: 6 -> 7 checks, real sample output,
  documentation of the four overall status categories.
- Removed the `model_unavailable health check` bullet from "What Does NOT Work Yet."
- `rejection_audit_disagreement` remains deferred.

### tests/test_ris_monitoring.py

Updated existing tests that assumed stub behavior:
- `test_model_unavailable_green_no_failures` — new behavior: GREEN means no data,
  not a hardcoded stub.
- `test_evaluate_health_returns_all_seven_checks` — 7 not 6.
- `ALL_CHECKS` length assertion updated to 7.
- `test_health_json_includes_deferred_checks` — model_unavailable no longer in
  deferred list.

Added two new test classes:
- `TestMetricsPhase2` — 6 tests covering provider routing, failure counts,
  review queue (including missing table), disposition distribution with BLOCKED
  detection, and routing summary.
- `TestHealthChecksPhase2` — 11 tests covering all threshold cases for both
  new checks, and `evaluate_health()` propagation of new kwargs.

## What Was Invisible Before

Before this work:

- `research-health` showed `model_unavailable: GREEN [stub - deferred]`
  regardless of whether any provider was actually failing.
- `research-stats summary --json` had no routing, failure, queue, or
  disposition fields — just raw gate counts and family breakdowns.
- Operators could not tell from health output whether the system was healthy
  because providers worked, or healthy because nothing had run yet.
- The "Overall" category did not exist; operators had to interpret raw RED/YELLOW.

After this work:

- `research-health` shows real provider failure data and review queue state.
- `Overall: HEALTHY / DEGRADED / BLOCKED_ON_SETUP / FAILURE` gives operators a
  single line they can act on.
- `research-stats summary --json` includes the 5 new Phase 2 fields for
  dashboards and export.

## Remaining Deferred

- `rejection_audit_disagreement` — still a stub. Requires an audit runner that
  samples rejected documents and re-scores them for disagreement detection.
  This is a Phase 3 / RIS v2 deliverable.

## Test Results

```
75 passed in 2.3s (tests/test_ris_monitoring.py)
```

All new tests pass; no regressions in existing tests.

## Codex Review

Tier: Skip (docs, tests, CLI formatting — no execution/kill-switch code touched).
