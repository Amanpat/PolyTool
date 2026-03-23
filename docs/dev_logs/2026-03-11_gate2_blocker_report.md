# Dev Log: Gate 2 Blocker Report

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track A — Phase 1

---

## Executive Summary

Gate 2 (Scenario Sweep) remains blocked. All Track A plumbing is complete and
tested. The sole remaining blocker is live executable-edge scarcity: no tape in
the current corpus has `executable_ticks > 0`, and the most recent operator
scans confirm this condition persists.

Gate 2 blocks only Track A promotion items (Gate 3, Stage 0, Stage 1). Track B
research workflows are unaffected. Retry is warranted only on a factual
trigger — not on a schedule.

---

## Operator Evidence (2026-03-11)

### tape-manifest

```
Total tapes:    12
Eligible tapes:  0   (executable_ticks > 0 required)
Mixed-regime coverage: BLOCKED (0 eligible tapes across required regimes)
```

No tape in the current corpus meets the simultaneous depth + edge condition
required for sweep eligibility.

### gate2-preflight

```
Status: BLOCKED
Reason: no eligible tapes; mixed-regime coverage cannot be satisfied
```

Exit code 2 (BLOCKED). Preflight checks passed individually for tooling health,
but the tape corpus check failed because `eligible_count == 0`.

### scan-gate2-candidates --all --top 20 --explain

All visible candidates returned status `DEPTH_ONLY`:
- `executable_ticks = 0` for every candidate
- `best_edge` remained negative on every scan snapshot (complement sum > 1.0
  on both legs at all observed ticks)
- Depth was present on some candidates (depth condition intermittently satisfied)
  but complement edge never coincided with sufficient depth

The `DEPTH_ONLY` classification means the sum-ask threshold was never breached
while depth was simultaneously adequate. No `EXECUTABLE` or `NEAR` candidate
appeared.

### make-session-pack

`make-session-pack` requires explicit `--markets` or `--watchlist-file` to
specify capture targets. `--regime` alone is not a discovery mechanism — it sets
the capture threshold and regime label for markets already identified. There is
no operator shortcut that automatically discovers Gate 2-eligible markets from
regime alone.

### market-scan

`market-scan` does not support a `--regime` flag. It ranks markets by the
general market-selection scorer (volume, spread, activity) and is not wired to
Gate 2 candidate ranking. Gate 2 candidate discovery runs through
`scan-gate2-candidates`, not `market-scan`.

---

## Root Cause Analysis

The blocker is **live executable-edge scarcity**, not missing plumbing.

| Component | Status |
|-----------|--------|
| Gate 2 tooling (`close_sweep_gate.py`, `scan-gate2-candidates`, `prepare-gate2`, `watch-arb-candidates`, `tape-manifest`) | Complete and tested |
| Gate 2 preflight CLI (`gate2-preflight`) | Operational (exit 2 = BLOCKED as expected) |
| Regime integrity contract (SPEC-0016) | Implemented; regime provenance fields present |
| Candidate ranking (SPEC-0017) | Implemented; `--explain` output readable |
| Regime-aware capture thresholds | Implemented and tested (2026-03-11 log) |
| Session pack + watcher wiring | Implemented (`make-session-pack`, updated `watch-arb-candidates`) |
| Live complement edge appearing simultaneously with sufficient depth | **Not observed in current market inventory** |

All infrastructure is ready. The only outstanding item is a qualifying live
dislocation.

---

## What Gate 2 Blocks (and What It Does Not)

Gate 2 blocks only the Track A promotion sequence:

```
Gate 2 (Scenario Sweep) -> Gate 3 (Shadow) -> Stage 0 (paper-live) -> Stage 1 (capital)
```

Gate 2 does **not** block:

- Track B research workflows (wallet-scan, alpha-distill, hypothesis registry,
  experiment skeleton, RAG, LLM bundle/save)
- Gate 1 (already PASSED) or Gate 4 (already PASSED)
- MarketMakerV0/V1 development and testing
- Adverse-selection signal work (already merged into simtrader)
- Any documentation or tooling improvements

Track A is optional. It is never default-on. Its gate-blocked status does not
affect the primary research loop.

---

## Retry Triggers

Do not retry Gate 2 on a schedule. Retry when one of the following factual
conditions is present:

1. **Catalyst window**: a major resolution event (game result, election call,
   vote close) within the next 4-6 hours for a tracked market — these windows
   historically produce complement mispricing.

2. **Operator-supplied target slugs**: the operator has specific market slugs
   from external research (news, odds movement, social signals) that suggest
   complement dislocation is likely. Supply via `--markets` or
   `--watchlist-file` to `watch-arb-candidates`.

3. **Materially different live inventory**: a new market scan (`scan-gate2-candidates
   --all --top 20`) shows at least one `NEAR` or `EXECUTABLE` candidate that
   was not visible in prior runs, indicating changed market conditions.

No retry is warranted if the next scan still returns all `DEPTH_ONLY` with
negative `best_edge` across all candidates.

---

## Track A Is Optional

Per PLAN_OF_RECORD.md §2 and ARCHITECTURE.md:

> Track A is optional. It is not required for Track B research workflows and is
> never enabled by default.

Per ROADMAP.md Track A section:

> Current blocker: edge scarcity / lack of qualifying live dislocations, not
> SimTrader plumbing

The Gate 2 blocked status is an honest reflection of live market conditions.
It is not a code defect, a missing feature, or a test failure. Track A
promotion is correctly gated and will proceed when the market provides a
qualifying dislocation.

---

## No Changes Required

This report is documentation only. The following are explicitly out of scope:

- No gate criteria changes
- No softening of the pass condition (`executable_ticks > 0`, `profitable_fraction >= 0.70`)
- No code patches
- No new branches
- No claim that Track A is complete (Track A promotion is gate-blocked)

---

## Next Operator Action

When a retry trigger fires:

```bash
# 1. Check current candidate landscape
python -m polytool scan-gate2-candidates --all --top 20 --explain

# 2. If NEAR or EXECUTABLE candidates appear, build a session pack
python -m polytool make-session-pack --markets <slug1> <slug2> --regime <regime>

# 3. Run bounded watch session
python -m polytool watch-arb-candidates --session-plan <pack.json> --duration 1800

# 4. Check tape eligibility
python -m polytool tape-manifest --tapes-dir artifacts/simtrader/tapes

# 5. If eligible tapes exist, run preflight and then Gate 2
python -m polytool gate2-preflight --tapes-dir artifacts/simtrader/tapes
python tools/gates/close_sweep_gate.py
```

Until a trigger fires, no action is required on Gate 2.

---

## References

- `docs/ROADMAP.md` — Track A gate checklist and current status
- `docs/CURRENT_STATE.md` — Gate status snapshot (2026-03-07)
- `docs/PLAN_OF_RECORD.md` — Track A optional scope statement
- `docs/ARCHITECTURE.md` — Optional execution loop diagram
- `docs/specs/SPEC-0011-live-execution-layer.md` — Gate model and hard promotion order
- `docs/specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md` — Regime integrity contract
- `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` — Candidate ranking and status codes
- `docs/dev_logs/2026-03-07_bounded_dislocation_capture_trial.md` — Last live watcher result
- `docs/dev_logs/2026-03-11_gate2_preflight_main_module_fix.md` — Preflight CLI restoration
- `docs/dev_logs/2026-03-11_regime_aware_capture_thresholds.md` — Capture threshold wiring
