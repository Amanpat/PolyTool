# Gold Tape Capture Path Hardening

**Date:** 2026-04-14
**Stream:** quick-260414-qre
**Status:** COMPLETE

---

## Summary

Two hardening changes to the shadow tape capture path that eliminate the path
drift bug and silent quality gap exposed by the Gate 2 fill diagnosis
(dev log 2026-04-14_gate2_fill_diagnosis.md).

**Change 1 -- Fix shadow tape write path**

Shadow captures were writing tapes to `artifacts/simtrader/tapes/<run_id>/`
while the CLI output printed `artifacts/tapes/shadow/<run_id>/`. This path
drift caused 96 tapes to be invisible to `corpus_audit` (which scans
`artifacts/tapes/gold`, `artifacts/tapes/silver`, `artifacts/tapes`).

The fix adds `DEFAULT_SHADOW_TAPE_DIR = Path("artifacts/tapes/shadow")` and
changes the `tape_dir` assignment in `_shadow()` to use it. The actual write
path now matches what the CLI prints and is within corpus_audit's default roots.

**Change 2 -- Post-capture tape validation**

New module `packages/polymarket/simtrader/tape_validator.py` with
`validate_captured_tape()` that runs inline after every shadow capture and
prints a PASS / BLOCKED / WARN verdict with a specific reason. This replaces
the silent accumulation of unusable tapes (Silver-style price-only captures).

Key BLOCKED case: tapes with no `book` events (price-only) are now immediately
flagged with `"price-only tape -- no L2 book events, fill engine will reject all
orders with book_not_initialized"`. The operator sees this before they run
corpus_audit.

---

## Root Cause Reference

See `docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md` for full diagnosis.
Key finding: Silver tapes contain only `price_2min_guide` events. `L2Book` never
initializes. Fill engine returns `book_not_initialized` on every tick. Zero fills
across all 9 qualifying benchmark tapes. The fix is Gold tape capture; this
hardening prevents silent waste of capture sessions on unusable tapes.

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `tools/cli/simtrader.py` | Modified | Add `DEFAULT_SHADOW_TAPE_DIR`, fix `tape_dir` assignment in `_shadow()`, wire tape validator output block |
| `packages/polymarket/simtrader/tape_validator.py` | Created | `TapeValidationResult` dataclass + `validate_captured_tape()` function |
| `tests/test_gold_capture_hardening.py` | Created | 10 deterministic tests covering path constant, BLOCKED/PASS/WARN cases, operator output |
| `docs/dev_logs/2026-04-14_gold_capture_hardening.md` | Created | This file |

---

## What Changed in simtrader.py

**Before:**
```python
DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")
...
tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / run_id
# Writes to: artifacts/simtrader/tapes/<run_id>/
# Prints:    artifacts/tapes/shadow/<run_id>/   <-- mismatch
```

**After:**
```python
DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")
DEFAULT_SHADOW_TAPE_DIR = Path("artifacts/tapes/shadow")
...
tape_dir = DEFAULT_SHADOW_TAPE_DIR / run_id
# Writes to: artifacts/tapes/shadow/<run_id>/
# Prints:    artifacts/tapes/shadow/<run_id>/   <-- match
```

The `run_dir` (at `DEFAULT_ARTIFACTS_DIR / "shadow_runs" / run_id`) was NOT
changed -- only the tape directory moves to the canonical location.

---

## Tape Validator Logic

`validate_captured_tape(tape_dir, min_effective_events=50)` checks in priority order:

1. **BLOCKED** -- no `events.jsonl` found
2. **BLOCKED** -- `events.jsonl` exists but `effective_events == 0` (empty)
3. **BLOCKED** -- no `event_type == "book"` events (price-only tape)
4. **WARN** -- `effective_events < min_effective_events` (too short for Gate 2)
5. **WARN** -- no `watch_meta.json` (corpus audit cannot assign bucket)
6. **PASS** -- all checks clear

Multiple WARN conditions are combined with "; ".
The validator is streaming (line-by-line JSON parse) and never loads the full
file into memory (addresses T-qre-03 DoS threat in the plan's threat model).

---

## Post-Capture Output (new)

After every shadow capture with tape recording, the operator now sees:

```
--- Tape Quality Check ---
  Result     : PASS
  tape has 312 effective events with L2 book data
  L2 book    : yes
  Events     : 624 raw, 312 effective (2 assets)
  Event types: price_change=580, book=44
--------------------------
```

Or for a price-only (Silver-style) capture:

```
--- Tape Quality Check ---
  Result     : BLOCKED
  price-only tape -- no L2 book events, fill engine will reject all orders with book_not_initialized
  L2 book    : NO
  Events     : 60 raw, 60 effective (1 assets)
  Event types: price_2min_guide=60
--------------------------
```

---

## Test Results

```
tests/test_gold_capture_hardening.py::TestCanonicalShadowPath::test_shadow_tape_dir_uses_canonical_path PASSED
tests/test_gold_capture_hardening.py::TestCanonicalShadowPath::test_shadow_tape_dir_under_corpus_audit_roots PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorBlocked::test_blocked_no_events_file PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorBlocked::test_blocked_price_only_tape PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorBlocked::test_blocked_empty_events_file PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorPass::test_pass_gold_tape_with_l2 PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorPass::test_pass_binary_tape_effective_events PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorWarn::test_warn_low_event_count PASSED
tests/test_gold_capture_hardening.py::TestTapeValidatorWarn::test_warn_missing_watch_meta PASSED
tests/test_gold_capture_hardening.py::TestOperatorOutput::test_verdict_block_contains_actionable_message PASSED

10 passed in 0.49s
```

Full regression suite:
```
python -m pytest tests/ -x -q --tb=short
1 failed, 2470 passed, 3 deselected, 19 warnings
```

The 1 failure (`test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success`)
is a pre-existing unrelated AttributeError in the research provider module confirmed
pre-existing before this work (see dev log 2026-04-14_gate2_corpus_visibility_and_ranking.md).

---

## What Was NOT Changed (Scope Discipline)

- No changes to `config/benchmark_v1.*` files
- No changes to BrokerSim core fill logic
- No changes to Gate 2 sweep logic or thresholds
- No changes to `DEFAULT_ARTIFACTS_DIR` (still `artifacts/simtrader`)
- No changes to `run_dir` assignment (stays at `artifacts/simtrader/shadow_runs/<run_id>`)
- No changes to corpus_audit DEFAULT_TAPE_ROOTS
- No changes to Silver tape reconstruction
- No weakening of gate language or validation criteria

---

## Codex Review

Tier: Skip (path constant fix and output formatting; no execution logic, no order
placement paths, no kill-switch or risk manager changes).
