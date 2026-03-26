# Phase 1B Recovery — Gate 2 Root Cause Analysis (2026-03-26)

## Summary

Gate 2 previously returned FAILED (exit 1) for a sub-50-tape corpus. This
was incorrect behavior: per spec, fewer than 50 eligible tapes (those meeting
`min_events`) should produce NOT_RUN (exit 0), not a FAILED verdict. This
session resolves that semantic bug, reconciles an authority conflict in
SPEC-0012, builds a per-tape diagnostic tool, and establishes the true root
cause of the Gate 2 block.

---

## 1. Authority Conflict Audit

| Document | Previous claim | Correct claim | Fix applied |
|---|---|---|---|
| `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` §2 | `market_maker_v0` is the canonical Phase 1 strategy | `market_maker_v1` (logit A-S) is canonical, promoted 2026-03-10 | Updated §2 with explicit upgrade note; updated all command examples |
| `docs/ARCHITECTURE.md` optional execution loop | `market_maker_v0` in 3 places | `market_maker_v1` | Updated all 3 occurrences |
| `tools/gates/close_mm_sweep_gate.py` default strategy | not set (inherits from mm_sweep.py) | `market_maker_v1` | No change needed — strategy comes from sweep config |

SPEC-0012 authority conflict introduced when `market_maker_v1` replaced v0 on
2026-03-10. The spec was never updated. Fix: SPEC-0012 §2 now reads:

> **Canonical Phase 1 strategy (updated 2026-03-10):** `market_maker_v1`
> (logit Avellaneda-Stoikov). `market_maker_v0` is retained in the codebase
> but is not the validation target. All Gate 2 sweeps use `market_maker_v1`.

---

## 2. Root Cause Analysis

### Gate 2 NOT_RUN — corpus too small

**Symptom**: Gate 2 exited with `gate_failed.json` and exit code 1 on a
benchmark_v1 corpus run.

**Correct behavior**: When `len(eligible_outcomes) < min_eligible_tapes`
(default 50), the gate should exit 0 with NOT_RUN status, not FAILED.

**Fix**: Added `min_eligible_tapes` parameter to `run_mm_sweep()`. After
building `eligible_outcomes`, if count is below threshold, returns
`MMSweepResult(gate_payload=None, ...)` and clears old artifacts.
`close_mm_sweep_gate.py` changed NOT_RUN from `return 1` to `return 0`.

### Per-tape diagnostic (9 qualifying tapes — all RAN_ZERO_PROFIT / no_touch)

Diagnostic run against `config/benchmark_v1.tape_manifest`:

| Status | Count | Fill Opportunity |
|---|---|---|
| SKIPPED_TOO_SHORT | 41 | none |
| RAN_ZERO_PROFIT | 9 | no_touch |
| RAN_POSITIVE | 0 | — |
| ERROR | 0 | — |

All 9 qualifying tapes are `near_resolution` Silver bucket. The strategy
does generate quotes (fill_opportunity = "no_touch"), but no counterparty
fills them in replay. Fills require a counterparty order crossing the spread.

**Root causes of zero fills on qualifying tapes:**

1. **Near-resolution Silver tape characteristics**: These tapes are
   reconstructed from `price_2min` data only (no pmxt/JB fills). Price
   movement is minimal near resolution — the market has already converged.
   A market-maker posting two-sided quotes on a converged market faces
   near-zero adverse selection, but also near-zero fill probability.

2. **Short tape duration**: Even the 9 qualifying tapes have just barely
   enough events to pass the `min_events=50` threshold. Longer tapes would
   provide more fill opportunities.

3. **Gold new_market tapes**: 5 Gold tapes (xrp, sol, btc, bnb, hype) have
   1–3 effective events each after deduplication. All 5 are SKIPPED_TOO_SHORT.
   These are live-recorded shadow tapes that ran for a short capture window.

**Key diagnostic insight**: The Gate 2 block is a corpus quality problem,
not a strategy bug. The market_maker_v1 strategy correctly generates quotes
on the qualifying tapes. The problem is that the benchmark_v1 corpus was
assembled without a minimum-events filter per tape, so 82% of tapes are too
short for a valid sweep scenario.

---

## 3. Next Blocker

Gate 2 requires a corpus of at least 50 tapes with `effective_events >= 50`.
Current corpus provides only 9 such tapes.

**Options to unblock Gate 2 (in priority order):**

1. **Lower `min_events` threshold**: If 10-20 events is sufficient for a
   meaningful single-scenario sweep, reducing `min_events` from 50 to e.g. 20
   would qualify more tapes. Risk: lower-event tapes may produce noisy results.
   Decision: requires operator judgment on acceptable statistical noise floor.

2. **Record longer Gold tapes**: Shadow mode can record live tapes. Running
   shadow sessions against active crypto/sports markets for 10-30 minutes
   should yield Gold tapes with hundreds of effective events each. 50 such
   tapes would fully satisfy Gate 2's corpus requirement.

3. **Reconstruct Silver tapes with pmxt+JB fills**: The gap-fill planner
   confirmed that politics/sports/crypto buckets have historical pmxt and JB
   coverage. Silver tapes reconstructed with actual fill events (not just
   price_2min) would have more effective events and would contain real fill
   opportunities for the market maker to respond to.

The fastest path is option 2 (Gold shadow tapes). This can be done without
any code changes — only a shadow recording session is needed.

---

## 4. Files Changed

### Modified

| File | Change |
|---|---|
| `tools/gates/mm_sweep.py` | Added `DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES=50`, `min_eligible_tapes` field on `MMSweepResult`, `min_eligible_tapes` param on `run_mm_sweep()`, NOT_RUN branch |
| `tools/gates/close_mm_sweep_gate.py` | NOT_RUN exits 0 (was 1); added `--min-eligible-tapes` CLI arg |
| `tools/cli/simtrader.py` | NOT_RUN exits 0; added `--min-eligible-tapes` to sweep-mm subparser |
| `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` | §2 updated to `market_maker_v1`; command examples updated; file reference added |
| `docs/ARCHITECTURE.md` | 3 occurrences of `market_maker_v0` → `market_maker_v1` in optional execution loop |
| `tests/test_mm_sweep_gate.py` | Added `min_eligible_tapes=3` to one test call; updated 2 NOT_RUN assertions (rc 1→0); added 3 new tests in `TestMinEligibleTapesNotRun` |
| `docs/CURRENT_STATE.md` | Updated heading and Gate 2 status section |

### Created

| File | Purpose |
|---|---|
| `tools/gates/mm_sweep_diagnostic.py` | Per-tape root cause diagnostic tool |
| `tests/test_mm_sweep_diagnostic.py` | 4 TDD tests for the diagnostic tool |

---

## 5. Test Counts

```
Full regression suite run on 2026-03-26 after all changes:
  2656 passed, 0 failed, 0 errors
```

Affected test files and counts:

| File | Tests | Result |
|---|---|---|
| `tests/test_mm_sweep_gate.py` | 18 | PASS |
| `tests/test_mm_sweep_diagnostic.py` | 4 | PASS |
| All other tests | 2634 | PASS (no regressions) |

TDD cycle for `mm_sweep_diagnostic.py`:

- RED commit (`62c637c`): 4 tests written, all failing (module did not exist)
- GREEN commit (`5c42d11`): implementation added, all 4 tests passing
- No REFACTOR step needed

---

## Commits

| Hash | Message |
|---|---|
| `9dad376` | fix(quick-026): resolve authority conflicts and fix Gate 2 NOT_RUN semantics |
| `62c637c` | test(quick-026): add failing tests for mm_sweep_diagnostic (TDD RED) |
| `5c42d11` | feat(quick-026): add mm_sweep_diagnostic.py for per-tape root cause analysis |

---

## Diagnostic Artifact

```
artifacts/gates/mm_sweep_gate/diagnostic/diagnostic_report.md
```

Full per-tape breakdown (50 rows) with: bucket, tier, effective_events,
status, quote_count, fill_opportunity, skip_reason. Summary section
shows fill opportunity distribution (none=41, no_touch=9).
