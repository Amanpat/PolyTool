# Feature: Phase 1 Gate 2 Candidate Ranking

**Spec**: `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Extends the Gate 2 candidate scan path to produce **explainable, multi-factor
rankings** so operators can prioritize watchlist markets during catalyst windows.

Previously, `scan-gate2-candidates` ranked by depth+edge signals only, with no
visibility into reward, volume, competition, or new-market context.

Now every candidate produces:
- A `Gate2RankScore` with a factor-by-factor breakdown
- A `gate2_status` summary code (EXECUTABLE / NEAR / EDGE_ONLY / DEPTH_ONLY / NO_SIGNAL)
- Explicit `UNKNOWN` labels for any factor where data is absent
- A `is_new_market` flag and regime label where available

---

## Changed files

| File | Change |
|------|--------|
| `packages/polymarket/market_selection/scorer.py` | Added `Gate2RankScore`, `GATE2_RANK_WEIGHTS`, `score_gate2_candidate`, `rank_gate2_candidates` |
| `tools/cli/scan_gate2_candidates.py` | Added `score_and_rank_candidates`, `print_ranked_table`; updated `main()` to use explainable path; added `--explain` flag |
| `tests/test_gate2_candidate_ranking.py` | New: 14 tests covering scoring, missing-data, new-market, ranking, integration |

---

## New CLI surface

```bash
# Ranked table with gate2_status, score, new-market flag, regime
python -m polytool scan-gate2-candidates --all --top 20

# Full factor breakdown per candidate
python -m polytool scan-gate2-candidates --all --top 20 --explain
```

### New output columns

```
Market                                       | Status | Score | Exec | BestEdge  | MaxDepth YES/NO  | New? | Regime
```

With `--explain`:
```
some-market-slug                             |   NEAR | 0.412 |    0 |  -0.0320  |        75 / 62   |    N | ?
    GATE2: NEAR — edge and depth both seen but never simultaneously
    depth: YES 75 / NO 62 — MEETS target (50 shares)
    edge: best_edge=-3.20% — sum_ask was 3.20% above threshold (not yet executable)
    reward: APR≈1.50/yr (HIGH)
    volume_24h: $28,000 (MED)
    competition: 0.50 (LOW CROWDING; 1 thin bid(s) < $50)
    age: 38.5h (mature; no new-market bonus)
    regime: UNKNOWN — not yet labeled; use --regime during tape capture
```

---

## Ranking factors (SPEC-0017 §2)

| Factor | Weight | Notes |
|--------|--------|-------|
| gate2_depth | 25% | min(depth_yes, depth_no) / max_size, capped at 1.0 |
| gate2_edge | 25% | best_edge normalized over [-0.10, +0.05] |
| reward | 20% | reward_rate * 365 / 3.0; UNKNOWN if no reward_config |
| volume | 15% | volume_24h / 50,000; UNKNOWN if no metadata |
| competition | 10% | 1/(thin_bids+1); UNKNOWN if no orderbook |
| age | 5% | 1.0 if new market (<48h), 0 otherwise; UNKNOWN if no created_at |

**Missing factors contribute zero, not positive evidence.**

---

## Key invariants preserved

- Gate 2 pass criteria unchanged: `executable_ticks > 0` in tape (via `close_sweep_gate.py`)
- Existing `rank_candidates()` and `print_table()` untouched (backward compatible)
- EXECUTABLE markets always sort first in `rank_gate2_candidates()`
- All existing `test_market_selection.py` tests still pass
