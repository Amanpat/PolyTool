# Dev Log: Coverage-Aware Session Pack Planning

**Date:** 2026-03-10
**Branch:** simtrader
**Spec:** SPEC-0018-gate2-capture-session-pack.md

---

## Problem

`make-session-pack` already reads the tape manifest and records `corpus_context`
(eligible_count, covered_regimes, missing_regimes) in the session plan.  But the
operator had no way to *act* on that information at selection time:

- Which of the scanned candidates would help fill the missing politics or
  new_market gap?
- If top-3 sports markets dominate the scan, how do you surface the one
  politics candidate without hand-picking?

---

## Solution

Added two advisory CLI flags and a `coverage_intent` field to `session_plan.json`.

### New flags

**`--prefer-missing-regimes`**
Reorders the merged candidate list so candidates whose probed regime matches a
missing regime (from `--source-manifest`) appear first — before `--top` is
applied.  If missing_regimes is empty (no manifest or all regimes covered), the
flag is a no-op with a warning.

**`--target-regime REGIME`**
Filters candidates to those matching `REGIME` before `--top`.  If no candidates
match, all are included with a stderr warning (advisory, never blocking).

### `coverage_intent` in session_plan.json

```json
"coverage_intent": {
  "prefer_missing": false,
  "target_regime": null,
  "missing_regimes_at_creation": ["politics", "new_market"],
  "advances_coverage": false,
  "coverage_warning": "NOTICE: None of the selected slugs target missing regimes ..."
}
```

`advances_coverage` is `true` when at least one selected slug's `final_regime`
is in the missing set, `false` when none do, and `null` when no manifest was
provided.

The `coverage_warning` message is also printed in the stdout summary so the
operator sees it without having to open the JSON.

---

## Regime probing design

Coverage-aware reorder/filter must happen **before** `--top` in `main()`, but
the full `final_regime` derivation happens inside `_build_watchlist_rows()`.

Approach: `_probe_target_regime()` probes each target cheaply:
1. Fast path: if the target carries a pre-computed `_regime` key (set by
   `_load_ranked_json()` from the ranked-scan artifact), return it directly.
2. Fallback: build a snapshot from target.metadata and call `derive_tape_regime()`
   exactly like `_build_watchlist_rows()` does.

The fast path means ranked-JSON inputs (the recommended workflow) get free,
accurate probing.  Watchlist-file or `--slugs` inputs fall back to the
snapshot classifier.

---

## Coverage invariants

- Coverage guidance is **advisory only** — Gate 2 pass criteria are unchanged.
- `--target-regime` never raises exit code 1 when no candidates match; the
  operator always gets a usable session pack.
- `advances_coverage=null` when manifest not provided (unknown state, not
  a warning condition).
- `coverage_intent` is always present in the plan; existing consumers that
  don't read it are unaffected.
- All existing tests continue to pass (71 total in test_gate2_session_pack.py).

---

## Files changed

| File | Change |
|------|--------|
| `tools/cli/make_session_pack.py` | Added `_probe_target_regime`, `_reorder_for_missing_regimes`, `_filter_by_target_regime`, `_build_coverage_intent`; updated `make_session_pack()`, `print_session_pack_summary()`, `build_parser()`, `main()` |
| `tests/test_gate2_session_pack.py` | 22 new tests (71 total, all passing) |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Phase 1.5 updated with new flags and examples |
| `docs/features/FEATURE-gate2-capture-session-pack.md` | Coverage-aware section added |
| `docs/dev_logs/2026-03-10_coverage_aware_session_pack.md` | This file |
| `docs/INDEX.md` | Updated feature entry |

## Intentionally deferred

- SPEC-0018 not modified (specs are read-only per CLAUDE.md project rules).
- No Gate 3, Stage 0/1, shadow, FastAPI, Grafana, or VPS changes.
- No changes to Gate 2 pass criteria or eligibility checks.
- Multi-session coverage aggregate view — out of scope.
