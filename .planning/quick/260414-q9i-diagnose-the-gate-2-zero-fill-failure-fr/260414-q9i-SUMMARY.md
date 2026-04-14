---
phase: quick
plan: 260414-q9i
subsystem: gates/diagnostic
tags: [gate2, fill-diagnostic, silver-tapes, root-cause, market-maker]
dependency_graph:
  requires: [benchmark_v1.tape_manifest, artifacts/tapes/silver/]
  provides: [tools/gates/gate2_fill_diagnostic.py, docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md]
  affects: [Gate 2 closure path]
tech_stack:
  added: []
  patterns: [tick-level tape replay, L2Book inspection, strategy intent analysis]
key_files:
  created:
    - tools/gates/gate2_fill_diagnostic.py
    - docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md
  modified: []
decisions:
  - Use ASCII double-dash instead of Unicode em dash in all CLI output (CLAUDE.md: prefer plain ASCII)
  - Manifest path fallback: when 50/50 entries missing, silently fall back to artifacts/tapes/silver/ scan
  - Read-only diagnostic only: no gate logic changes, no threshold changes, no simulator changes
metrics:
  duration: "~23 hours (session with context break)"
  completed: "2026-04-14"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Quick 260414-q9i: Diagnose Gate 2 Zero-Fill Failure -- Summary

**One-liner:** Silver tapes contain only `price_2min_guide` events; `L2Book._initialized` never becomes True; `fill_engine.try_fill()` returns `book_not_initialized` at the first guard, before any quote comparison occurs.

---

## Objective

Diagnose why all 9 qualifying benchmark tapes produce zero fills at all 5 spread
multipliers in the Gate 2 mm_sweep. Identify the root cause with code-level evidence.
Do not modify any gate logic, thresholds, or fill model behavior.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 01 | Multi-tape fill-path diagnostic script | 737641c | tools/gates/gate2_fill_diagnostic.py |
| 02 | Evidence-based dev log with root cause verdict | 1e9be74 | docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md |

---

## Root Cause Finding

**H1 CONFIRMED.** Silver tapes contain only `price_2min_guide` events. This is a
more severe version of H1 than originally hypothesized -- not "BBO-only depth" but
"zero L2 data at all."

Mechanism (confirmed by code inspection and diagnostic output):

1. Silver tapes: `event_type='price_2min_guide'` only. 528 events across 9 tapes. Zero `book` or `price_change` events.
2. `L2Book.apply()` handles only `EVENT_TYPE_BOOK` and `EVENT_TYPE_PRICE_CHANGE`. All other types return `False` with no state change.
3. `L2Book._initialized` stays `False` for the entire tape replay.
4. `fill_engine.try_fill()` first check: `if not book._initialized: return _reject("book_not_initialized")`. Quote comparison never occurs.
5. `MarketMakerV1` inherits `compute_quotes()` which returns `[]` when `best_bid is None or best_ask is None`. Since the book never initializes, both BBO values are always `None`, so the strategy emits zero `OrderIntent`s.

Result: 0/9 tapes with book initialized, 0 BUY intents, 0 fill opportunities, identical at 0.5x spread multiplier.

**H2 (resolution guard)** is secondary and currently untestable. 5/9 qualifying tapes
have resolution guard active (mid < 0.10 or > 0.90). Whether the 2.5x spread widening
would prevent fills on populated books is an open question deferred until H1 is resolved.

**H3 (inventory chicken-and-egg)** is a consequence of H1. The "Insufficient position
to reserve SELL order" ledger warning does not block order submission; it occurs because
BUY fills never happen.

**Fill engine and strategy: both correct.** The simulator is behaving exactly as designed.

---

## Diagnostic Tool Output (key metrics)

```
Tapes discovered : 118
  Qualifying (>= 50 events): 9
  Skipped (too short)      : 109

Event Type Survey: price_2min_guide = 528  (zero book-affecting events)

Cross-Tape Aggregate:
  Tapes where book initialized    : 0/9
  Total BUY intents               : 0
  BUY intents that would fill     : 0
  Overall fill opportunity rate   : N/A
```

---

## Side Finding: Manifest Path Mismatch

`config/benchmark_v1.tape_manifest` references `artifacts/silver/TOKEN_ID/DATE/silver_events.jsonl`.
Actual on-disk location: `artifacts/tapes/silver/TOKEN_ID/DATE/silver_events.jsonl`.
The missing `tapes/` infix causes all 50 manifest entries to fail path resolution.
The diagnostic script handles this with a fallback. The manifest is locked per
benchmark versioning ADR and must not be modified without operator decision.

---

## Recommended Next Actions

1. **PRIMARY UNBLOCK -- Gold tape capture.** Run `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`. Gold tapes contain `book` snapshots and `price_change` deltas. Gate 2 needs 50 qualifying Gold tapes (>= 50 effective events each).
2. **SECONDARY -- H2 diagnostic with Gold tapes.** Re-run `python tools/gates/gate2_fill_diagnostic.py --tapes-dir artifacts/tapes/gold` to determine if the resolution guard prevents fills on near_resolution markets even with a populated book.
3. **Do not modify gate logic.** The fill engine, thresholds, and eligibility criteria are correct. Fix the data, not the validator.

---

## Deviations from Plan

**1. [Rule 2 - Convention] ASCII output instead of Unicode em dashes**
- Found during: Task 1 (post-script-run)
- Issue: CLAUDE.md mandates "Prefer plain ASCII in logs and CLI output when possible." The script used Unicode em dash (`\u2014`) which rendered as `?` in Windows cp1252 console.
- Fix: Replaced all 6 Unicode em dashes with `--` (ASCII double dash) using a Python replacement pass.
- Files modified: tools/gates/gate2_fill_diagnostic.py
- Commit: included in 737641c

**2. [Rule 1 - Observation] H1 more severe than hypothesized**
- The original H1 hypothesis was "Silver tapes have BBO-only depth (no order book levels below the best ask)." The actual finding is "Silver tapes have zero L2 data -- not even a BBO." This is more definitive: the book never initializes at all, which is why BuyInts = 0 (not "BuyInts > 0 but WldFill = 0"). The diagnostic script correctly captures this distinction in its VERDICT logic.
- No code change required -- this is a finding refinement, not a bug.

---

## Known Stubs

None. The diagnostic script is complete and produces actionable output. The dev log
reflects actual diagnostic output numbers.

---

## Self-Check: PASSED

- `tools/gates/gate2_fill_diagnostic.py` exists on disk: CONFIRMED
- `docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md` exists on disk: CONFIRMED
- Commit 737641c exists: CONFIRMED
- Commit 1e9be74 exists: CONFIRMED
- Regression suite: 2460 passed, 1 pre-existing failure (test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success -- pre-dates this task, unrelated to gate2 diagnostics)
