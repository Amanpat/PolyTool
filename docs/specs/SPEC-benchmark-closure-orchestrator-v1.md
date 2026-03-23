# SPEC: Benchmark Closure Orchestrator v1

**Spec ID:** SPEC-benchmark-closure-orchestrator-v1
**Status:** Implemented (v0)
**Date:** 2026-03-17
**CLI:** `python -m polytool close-benchmark-v1`
**Module:** `tools/cli/close_benchmark_v1.py`

---

## Purpose

Single-command, operator-safe orchestration of the full benchmark_v1 tape
closure sequence.  The operator runs one command; the orchestrator preflights
the environment, runs Silver gap-fill and new-market capture in the correct
order, refreshes benchmark curation after each stage, and writes a single
machine-readable artifact recording whether `config/benchmark_v1.tape_manifest`
was created or what still blocks it.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | `config/benchmark_v1.tape_manifest` exists at end of run |
| 1 | Final status is `blocked` — quotas not met or stage errors |
| 2 | Preflight blocked — no mutations were attempted |

---

## Orchestration Stages

### Stage 1 — Preflight

Runs before any mutation.  Checks:

- Whether `config/benchmark_v1.tape_manifest` already exists (→ `already_closed`
  short-circuit, exit 0).
- Whether `config/benchmark_v1_gap_fill.targets.json` exists and is parseable.
- ClickHouse availability via HTTP `SELECT 1`.
- Count of priority-1 targets in the gap-fill manifest.
- Whether a prior new-market insufficiency report exists.
- Emits warnings (not blockers) for: ClickHouse unavailability, live
  connectivity requirement for new-market stage.

Status values: `ready` | `blocked` | `already_closed`.

### Stage 2 — Silver Gap-fill

Runs only if preflight passes and `--skip-silver` is not set.

1. Loads `config/benchmark_v1_gap_fill.targets.json` (schema
   `benchmark_gap_fill_v1`).
2. Extracts priority-1 token IDs.
3. Calls `fetch-price-2min` for those token IDs (skipped in `--dry-run` or
   `--skip-price-2min`).
4. Calls `run_batch_from_targets()` from `batch_reconstruct_silver` against all
   targets in the manifest.
5. Calls `_refresh_benchmark_curation()` — writes the manifest if quotas are
   now met, otherwise updates the gap report.

A failure in step 3 or 4 is recorded without aborting the stage or the run.

### Stage 3 — New-market Closure

Runs only if preflight passes and `--skip-new-market` is not set.

1. Calls `new-market-capture` planner (live Gamma API).  Writes
   `config/benchmark_v1_new_market_capture.targets.json` if candidates found.
2. If the planner returns exit 0 or 2 (some candidates) **and** the targets
   file exists: calls `capture-new-market-tapes --benchmark-refresh`.
3. If planner returns exit 1 (zero candidates): capture is skipped; the
   insufficiency is surfaced as a blocker in finalization.

Skipped entirely in `--dry-run`.

### Stage 4 — Finalization

Always runs (even if stages 2 or 3 were skipped).

- If `config/benchmark_v1.tape_manifest` exists: status `manifest_created`,
  tape count validated.
- Otherwise: reads `config/benchmark_v1.gap_report.json` for per-bucket
  shortages.  Reads `config/benchmark_v1_new_market_capture.insufficiency.json`
  for new_market blocker detail.  Status `blocked`.

---

## Run Artifact Contract

Path (canonical): `artifacts/benchmark_closure/<YYYY-MM-DD>/<run_id>/benchmark_closure_run_v1.json`
Path (override): `--out PATH`

```json
{
  "schema_version": "benchmark_closure_run_v1",
  "run_id": "<uuid>",
  "started_at": "<iso8601>",
  "completed_at": "<iso8601>",
  "dry_run": false,
  "final_status": "manifest_created | blocked",
  "preflight": {
    "status": "ready | blocked | already_closed",
    "checks": { ... },
    "blockers": [ ... ],
    "warnings": [ ... ]
  },
  "silver_gap_fill": {
    "status": "completed | dry_run | skipped | error",
    "targets_count": 120,
    "priority1_count": 39,
    "fetch_price_2min": { "status": "success | error | dry_run | skipped_flag", ... },
    "batch_reconstruct": { "targets_attempted": 120, "tapes_created": 39, ... },
    "benchmark_refresh": { "triggered": true, "manifest_written": false, ... }
  },
  "new_market_capture": {
    "status": "completed | dry_run | skipped",
    "planner": { "status": "success | insufficient | error", "return_code": 0, ... },
    "capture": { "status": "success | skipped | error", ... },
    "benchmark_refresh": { ... }
  },
  "finalization": {
    "status": "manifest_created | blocked | manifest_invalid",
    "manifest_path": "config/benchmark_v1.tape_manifest | null",
    "tape_count": 50,
    "blockers": [ "bucket 'new_market': shortage=5", ... ],
    "gap_report_path": "config/benchmark_v1.gap_report.json | null"
  },
  "residual_blockers": [ ... ],
  "manifest_path": "config/benchmark_v1.tape_manifest | null"
}
```

---

## CLI Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--dry-run` | off | Preflight + plan only; no mutations |
| `--skip-silver` | off | Skip Silver gap-fill stage |
| `--skip-new-market` | off | Skip new-market capture stage |
| `--out PATH` | canonical | Override run artifact output path |
| `--pmxt-root PATH` | None | pmxt_archive root for Silver reconstruction |
| `--jon-root PATH` | None | jon_becker root for Silver reconstruction |
| `--skip-price-2min` | off | Skip fetch-price-2min in Silver stage |
| `--clickhouse-*` | defaults | ClickHouse connection overrides |

---

## Resumability

- If `config/benchmark_v1.tape_manifest` exists at preflight time: immediately
  exits 0 (already closed) without running any mutation.
- Re-running after a partial run is safe: each Silver tape is written to its
  own canonical directory; the benchmark curation refresh is idempotent.

---

## Stage Isolation

- A failure in the Silver stage does not abort the new-market stage.
- A failure in the new-market planner (no candidates) records the outcome and
  surfaces it as a blocker; it does not abort finalization.
- Each stage records its own `status`, `started_at`, `completed_at`, and any
  errors in the run artifact.

---

## Reused Surfaces

| Called component | How called |
|-----------------|------------|
| `tools.cli.batch_reconstruct_silver.run_batch_from_targets` | Direct Python call |
| `tools.cli.batch_reconstruct_silver._refresh_benchmark_curation` | Direct Python call |
| `tools.cli.fetch_price_2min.main` | Direct Python call (injectable for tests) |
| `tools.cli.new_market_capture.main` | Direct Python call (injectable for tests) |
| `tools.cli.capture_new_market_tapes.main` | Direct Python call (injectable for tests) |

No subprocess spawning.  No business logic is duplicated.
