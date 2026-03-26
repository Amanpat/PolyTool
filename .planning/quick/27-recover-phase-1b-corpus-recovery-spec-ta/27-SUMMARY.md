---
phase: quick
plan: "027"
subsystem: gate2-corpus-recovery
tags: [corpus, gate2, tdd, runbook, spec]
dependency_graph:
  requires: [quick-026]
  provides: [corpus_audit_tool, recovery_corpus_spec, gold_capture_runbook]
  affects: [gate2, track1]
tech_stack:
  added: []
  patterns: [tdd_red_green, quota_cap_selection, tier_preference_gold_silver]
key_files:
  created:
    - docs/specs/SPEC-phase1b-corpus-recovery-v1.md
    - tools/gates/corpus_audit.py
    - tests/test_corpus_audit.py
    - docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
    - docs/dev_logs/2026-03-26_phase1b_corpus_recovery.md
  modified:
    - docs/CURRENT_STATE.md
    - .planning/STATE.md
decisions:
  - Quota caps applied inside audit_tape_candidates() not run_corpus_audit() — keeps function a complete single-call unit
  - Gold preferred over Silver for quota selection; within tier, higher effective_events wins
  - benchmark_v1 files (tape_manifest, lock.json, audit.json) are immutable — corpus_audit.py never writes to them
  - min_events=50 threshold is not softened — same threshold governs Gate 2
  - Partial manifest is never written — manifest only on exit 0 (corpus qualified)
metrics:
  duration_minutes: 60
  completed_date: "2026-03-26"
  tasks_completed: 5
  files_changed: 7
---

# Quick 027: Corpus Recovery Tooling for Gate 2 Summary

**One-liner:** Recovery corpus audit pipeline with Gold>Silver quota selection, shortage reporting, and operator runbook for Gate 2 unblock.

## Objective

Build the tooling and spec to create a recovery corpus separate from the finalized `benchmark_v1`, quantify the current shortage, and direct the operator to the correct next action (Gold shadow tape capture).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | SPEC-phase1b-corpus-recovery-v1.md | a6031b9 | docs/specs/SPEC-phase1b-corpus-recovery-v1.md |
| 2 | TDD RED + GREEN corpus_audit.py | 210bef6, 9e0e6e8 | tests/test_corpus_audit.py, tools/gates/corpus_audit.py |
| 3 | Execute corpus audit, write dev log | 0eb13c8 | docs/dev_logs/2026-03-26_phase1b_corpus_recovery.md |
| 4 | CORPUS_GOLD_CAPTURE_RUNBOOK.md | 160a8d6 | docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md |
| 5 | Update CURRENT_STATE.md + STATE.md | 87d6f9c | docs/CURRENT_STATE.md, .planning/STATE.md |

## Implementation Details

### corpus_audit.py

Core functions:
- `audit_tape_candidates(tape_dirs, *, min_events=50) -> list[dict]` — Evaluates each tape dir. Rejection reasons: `too_short` (effective_events < min_events), `no_bucket_label` (no metadata chain yields bucket), `over_quota` (bucket filled). Quota selection: Gold first, then Silver; within tier, higher effective_events first.
- `run_corpus_audit(*, tape_roots, out_dir, min_events, manifest_out) -> int` — Discovers tape dirs via `_discover_tape_dirs()`, calls `audit_tape_candidates()`, writes manifest (exit 0) or shortage report (exit 1).
- `_discover_tape_dirs(root) -> list[Path]` — Recursive walk up to depth 4; returns dirs containing events.jsonl or silver_events.jsonl; stops descending once a tape dir is found.

Imports `_count_effective_events` and `_read_json_object` from `tools.gates.mm_sweep`.

Bucket detection priority: `watch_meta.json["bucket"]` > `market_meta.json["benchmark_bucket"]` > `market_meta.json["category"]` > `meta.json["regime"]`.

Bucket quotas: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5 (total 50).

### Corpus Audit Result

137 tapes scanned across artifacts/simtrader/tapes, artifacts/silver, artifacts/tapes:
- 9 accepted (all near_resolution Silver, effective_events >= 50)
- 128 rejected (119 too_short, 9 no_bucket_label)

Verdict: SHORTAGE (exit 1). Shortage report written to `artifacts/corpus_audit/shortage_report.md`.

Shortages: sports=15, politics=10, crypto=10, new_market=5, near_resolution=1.

### TDD Tests

6 tests in `tests/test_corpus_audit.py`:
1. `test_qualified_tape_accepted` — ACCEPTED status, effective_events >= 50, bucket set
2. `test_too_short_tape_rejected` — REJECTED with reason `too_short`
3. `test_no_bucket_label_rejected` — REJECTED with reason `no_bucket_label`
4. `test_quota_cap_per_bucket` — 17 sports tapes → 15 ACCEPTED, 2 `over_quota`
5. `test_shortage_when_below_50` — exit 1, shortage_report.md written, manifest NOT written
6. `test_qualified_manifest_written_when_sufficient` — exit 0, manifest written with 50 entries

All 6 pass. Full suite: 2662 passed, 0 failed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Quota caps were not applied inside audit_tape_candidates()**

- **Found during:** Task 2 (TDD GREEN)
- **Issue:** Test 4 (`test_quota_cap_per_bucket`) called `audit_tape_candidates()` directly and expected 15 accepted / 2 over_quota from 17 sports tapes. The initial design put quota caps only in `run_corpus_audit()`, so the direct call returned 17 accepted.
- **Fix:** Moved `_apply_quota_caps()` call inside `audit_tape_candidates()` so it is always applied. Updated `run_corpus_audit()` to call `audit_tape_candidates()` directly.
- **Files modified:** tools/gates/corpus_audit.py
- **Commit:** 9e0e6e8

**2. [Rule 1 - Bug] artifacts/ gitignored**

- **Found during:** Task 3 commit
- **Issue:** Attempted to commit `artifacts/corpus_audit/shortage_report.md`. Git rejected it because `artifacts/` is in `.gitignore`. This is correct behavior.
- **Fix:** Only committed the dev log file. Artifact files are intentionally gitignored.
- **Files modified:** none (no fix needed)
- **Commit:** 0eb13c8

## Known Stubs

None. All logic is fully implemented. The shortage_report.md is a runtime artifact reflecting the current tape inventory state.

## Open Work / Blockers

**Gate 2 corpus shortage remains.** The tooling is shipped; the tapes must still be captured.

- sports: need 15 more tapes
- politics: need 10 more tapes
- crypto: need 10 more tapes
- new_market: need 5 more tapes
- near_resolution: need 1 more tape

Resolution: Use `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` to capture Gold shadow tapes for each shortage bucket. Run `corpus_audit.py` after each batch. When exit 0, `config/recovery_corpus_v1.tape_manifest` is written and Gate 2 rerun is unblocked.

Track 2 blocker (crypto market availability) is unchanged by this task.
