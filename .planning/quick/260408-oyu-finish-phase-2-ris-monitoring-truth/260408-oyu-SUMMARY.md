---
phase: quick-260408-oyu
plan: 01
subsystem: ris-monitoring
tags: [ris, monitoring, health-checks, metrics, phase2]
dependency_graph:
  requires: []
  provides:
    - Phase 2 RIS metrics (routing, failures, queue, dispositions)
    - Real model_unavailable health check
    - review_queue_backlog health check
    - overall_category in research-health output
  affects:
    - research-health CLI
    - research-stats CLI
    - RIS operator visibility
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN for health check and metrics expansion
    - SQLite read-only query with graceful OperationalError handling
    - Dataclass field(default_factory=dict) for backward-compatible new fields
key_files:
  created:
    - docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
  modified:
    - packages/research/metrics.py
    - packages/research/monitoring/health_checks.py
    - tools/cli/research_health.py
    - docs/RIS_OPERATOR_GUIDE.md
    - tests/test_ris_monitoring.py
decisions:
  - "Use failure_reason keys (not provider_name keys) in provider_failure_counts for model_unavailable YELLOW trigger — reason-based aggregation is more actionable than per-provider counts"
  - "BLOCKED_ON_SETUP category checks only provider_unavailable failure reasons — other failure types (rate_limited, timeout) signal real operational issues not setup gaps"
  - "review_queue reads from ks_path (same DB as KnowledgeStore) rather than a separate path arg — avoids adding yet another path override to the CLI"
metrics:
  duration: ~25 minutes
  completed: "2026-04-08"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 5
  files_created: 1
  tests_added: 17
  tests_total: 75
---

# Phase quick-260408-oyu Plan 01: Finish Phase 2 RIS Monitoring Truth — Summary

**One-liner:** RIS health checks expanded from 6 stub-heavy checks to 7 real checks, with provider routing/failure/queue/disposition metrics and operator-facing HEALTHY/DEGRADED/BLOCKED_ON_SETUP/FAILURE category output.

## What Was Built

### Task 1: Expand metrics collection and wire deferred health checks

**packages/research/metrics.py** gained 5 new fields on `RisMetricsSnapshot`:

- `provider_route_distribution` — count per `selected_provider` from eval artifact `routing_decision` data.
- `provider_failure_counts` — count per `failure_reason` from `provider_events` with non-success status.
- `review_queue` — `queue_depth`, `by_status`, `by_gate` from read-only SQL on `pending_review` table. Handles missing table (fresh DBs) via `sqlite3.OperationalError` catch.
- `disposition_distribution` — ACCEPT/REVIEW/REJECT/BLOCKED counts. BLOCKED = gate REJECT where `scores.reject_reason == "scorer_failure"`.
- `routing_summary` — `escalation_count`, `fallback_count`, `direct_count`, `total_routed` from routing decision flags.

`format_metrics_summary()` updated with 4 new sections: Provider Routing, Provider Failures, Review Queue, Dispositions.

**packages/research/monitoring/health_checks.py** changes:

- `_check_model_unavailable()` stub replaced with real implementation accepting `provider_failure_counts` and `routing_config`. GREEN/YELLOW(>3 failures)/RED(all providers failing). No longer returns `deferred=True` or `check_type="stub"`.
- New `_check_review_queue_backlog(review_queue)` added. GREEN(depth<=20)/YELLOW(>20)/RED(>50).
- `evaluate_health()` updated to accept `provider_failure_counts`, `review_queue`, `routing_config` kwargs. Returns 7 results (was 6).
- `ALL_CHECKS` registry updated to 7 entries with accurate descriptions.

### Task 2: Wire CLI, add overall_category, update operator guide

**tools/cli/research_health.py:**

- Calls `collect_ris_metrics()` after loading runs to extract `provider_failure_counts` and `review_queue`, passes them to `evaluate_health()`.
- New `_determine_overall_category()` maps results to HEALTHY/DEGRADED/BLOCKED_ON_SETUP/FAILURE.
- `_output_table()` prints `Overall: {category}` after check table; BLOCKED_ON_SETUP shows setup hint.
- `_output_json()` includes `overall_category` field.
- Footer note preserved for `rejection_audit_disagreement` only (model_unavailable no longer deferred).

**docs/RIS_OPERATOR_GUIDE.md:**

- Health monitoring section updated: 6->7 checks, real sample output with table format, four overall status categories documented.
- Removed `model_unavailable health check` from "What Does NOT Work Yet" list.
- `rejection_audit_disagreement` remains documented as deferred.

## Verification

CLI smoke tests passed:
- `research-health --json`: 7 checks, `overall_category: FAILURE` (real pipeline issue in env), `deferred_checks: ["rejection_audit_disagreement"]`, model_unavailable not in deferred.
- `research-stats summary --json`: all 5 Phase 2 fields present including live `review_queue: {queue_depth: 1}`.

Full test suite: **3810 passed, 0 failed** (116.86s).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | 946677e | feat: expand Phase 2 metrics and wire real health checks |
| 2    | bab54ce | feat: wire Phase 2 metrics into CLI, add overall_category, update guide |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `rejection_audit_disagreement` health check: still returns GREEN stub with `[DEFERRED]` message. Requires audit runner to sample and re-score rejected documents. This is a planned Phase 3 / RIS v2 deliverable. Documented in RIS_OPERATOR_GUIDE.md.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. All SQLite access is read-only on existing DB.

## Self-Check
