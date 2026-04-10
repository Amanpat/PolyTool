---
phase: quick-260410-iz5
plan: "01"
subsystem: gates/simtrader
tags: [gate2, zero-fill, diagnosis, silver-tapes, root-cause]
dependency_graph:
  requires: [benchmark_v1_manifest, mm_sweep_gate]
  provides: [gate2_zero_fill_root_cause_evidence, diagnose_zero_fill_tool]
  affects: [tools/gates/mm_sweep.py, config/benchmark_v1.tape_manifest]
tech_stack:
  added: []
  patterns: [tick-level replay, fill engine instrumentation, L2Book inspection]
key_files:
  created:
    - tools/gates/diagnose_zero_fill.py
    - tests/test_diagnose_zero_fill.py
    - docs/dev_logs/2026-04-10_gate2_zero_fill_root_cause.md
  modified: []
decisions:
  - "Diagnostic tool only — no changes to simulator, fill engine, or Silver reconstruction pipeline"
  - "Root cause is TAPE QUALITY (Silver tapes have no L2 snapshots), not a simulator defect"
  - "Option A (synthetic snapshot injection) vs Option B (Gold corpus expansion) deferred to operator"
metrics:
  duration_minutes: 25
  completed: "2026-04-10"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase quick-260410-iz5 Plan 01: Gate 2 Zero-Fill Diagnosis Summary

**One-liner:** Tick-level diagnostic confirms Silver tapes contain only `price_2min_guide` events — L2Book never initializes, fill engine rejects 100% of attempts with `book_not_initialized`.

---

## What Was Built

### Task 1 — Diagnostic Script and Tests (commit `99a7e69`)

`tools/gates/diagnose_zero_fill.py` — 583-line single-tape deep diagnostic tool.

- Loads `silver_events.jsonl` (Silver) or `events.jsonl` (Gold) automatically
- Replays every tick: applies events to L2Book, calls MarketMakerV1.on_event, submits
  OrderIntents to SimBroker, captures fill rejection reasons from FillRecord.reject_reason
- Inspects `L2Book._initialized` and book depth at every tick
- Tracks per-tick quote samples (bid_crosses_ask, ask_crosses_bid)
- Tracks reservation blocks (sell_insufficient_position)
- Produces structured JSON verdict: BOOK_NEVER_INITIALIZED | NO_COMPETITIVE_LEVELS |
  RESERVATION_BLOCKED | QUOTES_TOO_WIDE | FILLS_OK | UNKNOWN
- CLI: `--tape-dir`, `--asset-id`, `--out`, `--verbose`

`tests/test_diagnose_zero_fill.py` — 3 offline tests (all using `tmp_path` fixture):

1. `test_book_never_initialized_verdict` — price_2min_guide-only tape, expects BOOK_NEVER_INITIALIZED
2. `test_book_initialized_no_competitive_levels` — wide-spread book, expects NO_COMPETITIVE_LEVELS/QUOTES_TOO_WIDE
3. `test_book_initialized_with_fills` — book snapshot then aggressive ask drop, expects FILLS_OK

All 3 tests passed.

### Task 2 — Diagnostic Runs and Dev Log (commit `8bb5f73`)

Ran `diagnose_zero_fill.py` against 3 representative tapes:

| Tape | Tier | total_events | book_affecting | book_init | verdict |
|---|---|---|---|---|---|
| 1029598904689285/2026-03-15T10-01-14Z | silver | 29 | 0 | false | BOOK_NEVER_INITIALIZED |
| 1630984922783900/2026-03-15T10-00-01Z | silver | 60 | 0 | false | BOOK_NEVER_INITIALIZED |
| bitboy-convicted/20260306T003541Z | gold | 5 | 4 | true (seq=0) | RESERVATION_BLOCKED |

`docs/dev_logs/2026-04-10_gate2_zero_fill_root_cause.md` — root cause evidence, bucket
classification, code path walkthrough, and next-step options for operator decision.

---

## Root Cause

**Silver tapes contain only `price_2min_guide` events.**

`L2Book.apply()` only handles `EVENT_TYPE_BOOK` and `EVENT_TYPE_PRICE_CHANGE`. All
`price_2min_guide` events return `False` from `apply()` without updating `_initialized`.

`fill_engine.try_fill()` first check:
```python
if not book._initialized:
    return _reject("book_not_initialized")
```

With `_initialized=False` for the entire replay, zero fill attempts are ever made.
This is a **tape quality limitation**, not a simulator defect.

The Silver reconstruction pipeline (`batch-reconstruct-silver`) synthesizes tapes from
2-minute price-guide data which contains only best_bid/best_ask reference points — no
L2 order book depth. Real L2 snapshots only exist in Gold tapes (live WebSocket output).

---

## Gate 2 Impact

| Metric | Value |
|---|---|
| Benchmark tapes total | 50 |
| Silver tapes (zero-fill) | ~43 |
| Gold tapes (positive) | 7 |
| Current pass_rate | 0.14 |
| Required pass_rate | 0.70 |
| Gap | 28 additional positive tapes |

---

## Deviations from Plan

None — plan executed exactly as written. Both files (`diagnose_zero_fill.py` and
`tests/test_diagnose_zero_fill.py`) were already committed by the previous executor
before hitting a rate limit. This session resumed from Task 2 (dev log), verified
the test suite (3/3 passed), ran the diagnostic against real tapes, and wrote the
dev log.

---

## Decisions Made

1. **Diagnostic tool is read-only** — does not modify any existing simulator or
   fill-engine code. Instrumentation is performed by calling existing public APIs
   in a new script.
2. **Root cause is tape quality** — confirmed by evidence; not a simulator defect.
3. **Next steps deferred to operator** — Option A (synthetic snapshot injection)
   requires a spec and architectural decision; Option B (Gold corpus expansion) is
   already the stated policy (ADR: WAIT_FOR_CRYPTO).

---

## Open Questions / Deferred Items

- Option A feasibility: injecting a synthetic `book` event from `price_2min_guide`
  best_bid/best_ask into Silver replay would require modifying the replay loader or
  adding a pre-processing step in mm_sweep.py. This is an architectural change (new
  data path) requiring a separate spec and operator approval.
- Should Gate 2 corpus be rebased on a newer Silver reconstruction that includes
  real L2 data? Requires checking whether any reconstruction path can produce real
  book snapshots from available data sources.

---

## Self-Check: PASSED

- tools/gates/diagnose_zero_fill.py: FOUND
- tests/test_diagnose_zero_fill.py: FOUND
- docs/dev_logs/2026-04-10_gate2_zero_fill_root_cause.md: FOUND
- Commit 99a7e69 (Task 1): FOUND
- Commit 8bb5f73 (Task 2): FOUND
- 3 tests: PASSED
- Full regression: 2452 passed (1 pre-existing unrelated failure in test_ris_phase2_cloud_provider_routing.py)
