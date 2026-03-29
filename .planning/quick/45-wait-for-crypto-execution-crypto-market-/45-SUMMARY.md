---
phase: quick-045
plan: 01
subsystem: gates
tags: [gate2, mm_sweep, corpus, shadow_capture, market_maker_v1, recovery_corpus]

# Dependency graph
requires:
  - phase: quick-041
    provides: Gold capture wave 2 (40/50 corpus), artifacts/tapes/shadow/ hierarchy
  - phase: quick-026
    provides: Gate 2 NOT_RUN semantics, mm_sweep gate infrastructure
provides:
  - config/recovery_corpus_v1.tape_manifest (50 entries, all qualifying tapes)
  - tools/gates/run_recovery_corpus_sweep.py (recovery corpus sweep driver)
  - Gate 2 sweep result: FAILED (7/50 positive, 14%)
  - artifacts/gates/mm_sweep_gate/gate_failed.json
  - docs/dev_logs/2026-03-29_crypto_watch_and_capture.md
affects: [gate2-path-forward, market_maker_v1-calibration, benchmark_v2-consideration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recovery corpus sweep driver: bypasses list-format manifest incompatibility with close_mm_sweep_gate.py by reading recovery_corpus_v1.tape_manifest directly"
    - "require_selected=False in _build_tape_candidate bypasses legacy selection filter for Gold shadow tapes"

key-files:
  created:
    - tools/gates/run_recovery_corpus_sweep.py
    - config/recovery_corpus_v1.tape_manifest
    - docs/dev_logs/2026-03-29_crypto_watch_and_capture.md
  modified:
    - docs/CURRENT_STATE.md

key-decisions:
  - "Gate 2 FAILED: 7/50 positive (14%), corpus is 50/50, silver tapes produce zero fills, non-crypto shadow tapes negative on low-frequency markets"
  - "Created run_recovery_corpus_sweep.py to bypass close_mm_sweep_gate.py format incompatibility (benchmark_v1.tape_manifest is dict-format, recovery_corpus_v1.tape_manifest is list-format)"
  - "Three path-forward options documented: crypto-only corpus subset, strategy improvement, Track 2 focus while Gate 2 research continues"

patterns-established:
  - "Recovery corpus manifest is plain JSON list of events.jsonl paths, written by corpus_audit.py, NOT compatible with close_mm_sweep_gate.py"

requirements-completed: []

# Metrics
duration: ~4h (including ~3h for crypto tape sweep)
completed: 2026-03-29
---

# quick-045: Crypto Watch and Capture + Gate 2 Summary

**Full 50-tape recovery corpus Gate 2 sweep ran and FAILED at 14% (7/50 positive, threshold 70%); root cause is zero fills on silver tapes and negative PnL on low-frequency non-crypto markets; crypto 5m tapes are 7/10 positive**

## Performance

- **Duration:** ~4 hours (majority: crypto tape sweep, ~20 min per tape x 10 crypto tapes)
- **Started:** 2026-03-29 (early morning, crypto market detection)
- **Completed:** 2026-03-29T12:32:30Z (gate_status written)
- **Tasks:** 3 (Task 1: preflight/watcher; Task 2: checkpoint decision "proceed-capture"; Task 3: Branch B full execution)
- **Files modified:** 4

## Accomplishments

- Crypto markets (BTC, ETH, SOL 5m) confirmed active on Polymarket 2026-03-29 morning; 14 shadow sessions captured
- Path drift fix: moved 14 shadow tapes from `artifacts/simtrader/tapes/` to `artifacts/tapes/shadow/` canonical path
- corpus_audit ran and exited 0 (50/50): all 5 buckets complete (politics=10, sports=15, crypto=10, near_resolution=10, new_market=5)
- Created `tools/gates/run_recovery_corpus_sweep.py` to handle manifest format incompatibility between `close_mm_sweep_gate.py` (benchmark dict-format) and `recovery_corpus_v1.tape_manifest` (list-format)
- Gate 2 sweep ran all 50 tapes; gate FAILED at 14% (7/50 positive, threshold 70%)
- Gate status, per-tape PnL breakdown, and root-cause analysis documented in dev log

## Task Commits

Note: Task 1 and Task 2 were executed in a prior session (context reset before commit). The work was completed atomically but the commits will be combined in the final metadata commit.

1. **Task 1: Preflight + one-shot availability check** - prior session (no separate commit; evidence in dev log)
2. **Task 2: Branch decision checkpoint** - operator replied "proceed-capture"
3. **Task 3: Branch B execution** - work performed across two sessions due to context limit

**Sweep driver + manifest + dev log + CURRENT_STATE.md updates:** committed together in final plan commit

## Files Created/Modified

- `tools/gates/run_recovery_corpus_sweep.py` - Recovery corpus sweep driver; reads list-format manifest, calls `_build_tape_candidate(..., require_selected=False)`, runs mm_sweep inner loop for all 50 tapes
- `config/recovery_corpus_v1.tape_manifest` - Plain JSON list of 50 events.jsonl paths (10 silver + 40 shadow); written by corpus_audit.py
- `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md` - Full verbatim sweep output, gate_status output, per-tape PnL table, root-cause analysis, path-forward options
- `docs/CURRENT_STATE.md` - Gate 2 status updated from NOT_RUN (40/50) to FAILED (7/50 = 14%, 50/50 corpus); next-executable-step section updated with three path-forward options

## Decisions Made

- **run_recovery_corpus_sweep.py created** instead of fixing close_mm_sweep_gate.py format incompatibility: the benchmark manifest uses dict-format (with "selected": true entries) while recovery_corpus_v1.tape_manifest uses plain list-format. Fixing close_mm_sweep_gate.py would risk touching benchmark_v1 manifest handling; a separate driver is cleaner.
- **Gate 2 result = FAILED not NOT_RUN**: corpus is 50/50, sweep ran, 7/50 positive < 70% threshold. Per spec, FAILED = corpus ran but did not meet threshold.
- **Three path-forward options documented** in dev log rather than autonomously choosing one: (1) crypto-only corpus subset (7/10 = 70%, requires spec change + operator auth), (2) strategy improvement (research path), (3) Track 2 focus while Gate 2 research continues.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created run_recovery_corpus_sweep.py to handle manifest format mismatch**
- **Found during:** Task 3 Step B5 (Gate 2 sweep attempt)
- **Issue:** `close_mm_sweep_gate.py` reads dict-format manifests with `"selected": true` entries; `recovery_corpus_v1.tape_manifest` is a plain JSON list. Running close_mm_sweep_gate.py against the recovery manifest would fail to discover any tapes.
- **Fix:** Created `tools/gates/run_recovery_corpus_sweep.py` that reads the list-format manifest directly, calls `_build_tape_candidate(..., require_selected=False)` for each entry, and replicates the mm_sweep inner loop.
- **Files modified:** `tools/gates/run_recovery_corpus_sweep.py` (created)
- **Verification:** Sweep ran all 50 tapes, wrote `gate_failed.json` with expected keys (`tapes_total=50`, `tapes_positive=7`, `pass_rate=0.14`)
- **Committed in:** final plan metadata commit

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix — without it Gate 2 could not run against the recovery corpus. No scope creep.

## Gate 2 Sweep Results Summary

| Category | Count | Positive | Notes |
|----------|-------|----------|-------|
| Silver tapes | 10 | 0 | Zero fills — no tick density for MM orders |
| Shadow non-crypto | 30 | 0 | Mostly net=n/a or small negative; low-frequency markets |
| Crypto BTC 5m | 5 | 4 | +$35.54, +$8.79, +$5.93, +$4.67, -$19.90 |
| Crypto ETH 5m | 2 | 2 | +$297.25, +$99.81 |
| Crypto SOL 5m | 3 | 1 | -$492.34, -$34.59, +$183.48 |
| **Total** | **50** | **7** | **14% (need 70%)** |

Gate artifact: `artifacts/gates/mm_sweep_gate/gate_failed.json`

## Issues Encountered

- **Context reset mid-sweep:** The Gate 2 sweep (50 tapes, ~20 min per crypto tape) exceeded one session context limit at tape [41/50]. A new session re-ran the sweep from scratch (prior artifact results were overwritten). Final sweep output was read from background task output file.
- **Silver tapes produce zero fills:** `net=n/a positive=False` for all 10 silver tapes. This is structural — silver tapes from pmxt reconstruction lack the tick density needed for market maker fills. These tapes are not useful for Gate 2 MM validation.
- **Non-crypto shadow tapes mostly negative:** Low-frequency politics/sports markets have insufficient order flow for the market_maker_v1 strategy to generate positive PnL after fees.

## Next Phase Readiness

Gate 2 is FAILED. Gate 3 remains BLOCKED. Three path-forward options are documented:
1. Crypto-only corpus subset test (requires operator authorization for spec change)
2. Strategy improvement research for market_maker_v1 on low-frequency tapes
3. Track 2 (crypto pair bot) independent deployment while Gate 2 research continues

Track 2 does NOT require Gate 2 to pass — it is standalone per CLAUDE.md policy.

---
*Phase: quick-045*
*Completed: 2026-03-29*

## Self-Check: PASSED

- FOUND: tools/gates/run_recovery_corpus_sweep.py
- FOUND: config/recovery_corpus_v1.tape_manifest
- FOUND: docs/dev_logs/2026-03-29_crypto_watch_and_capture.md
- FOUND: .planning/quick/45-wait-for-crypto-execution-crypto-market-/45-SUMMARY.md
- FOUND: artifacts/gates/mm_sweep_gate/gate_failed.json (verified via prior session reads)
