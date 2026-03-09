# Dev Log: Phase 1 Gate 2 Candidate Ranking

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What was built

Extended the Gate 2 candidate scan path (`scan-gate2-candidates`) to produce
explainable, multi-factor rankings as specified in SPEC-0017.

### Problem

`scan-gate2-candidates` ranked by depth+edge only. Operators could not see why
a market ranked high, whether it was a new market, or what reward/volume/
competition context existed. Missing data was invisible.

### Solution

Added `Gate2RankScore` (new dataclass in `scorer.py`) that combines Gate 2 signals
with market quality factors. `score_gate2_candidate()` produces one score per
candidate with a human-readable explanation list. Missing factors emit `UNKNOWN`.

`rank_gate2_candidates()` sorts by: executable_ticks -> rank_score -> edge -> depth.

`scan_gate2_candidates.py` gains `score_and_rank_candidates()` (wraps CandidateResult
list) and `print_ranked_table()` (new output with status/score/new/regime columns).

`--explain` flag prints the full factor breakdown after each table row.

---

## Files changed

| File | What changed |
|------|-------------|
| `packages/polymarket/market_selection/scorer.py` | +`Gate2RankScore`, +`GATE2_RANK_WEIGHTS`, +`score_gate2_candidate()`, +`rank_gate2_candidates()` |
| `tools/cli/scan_gate2_candidates.py` | +`score_and_rank_candidates()`, +`print_ranked_table()`, +`--explain` flag, updated `main()` |
| `tests/test_gate2_candidate_ranking.py` | New file: 14 tests |
| `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` | New spec |
| `docs/features/FEATURE-phase1-gate2-candidate-ranking.md` | New feature doc |
| `docs/dev_logs/2026-03-08_phase1_gate2_candidate_ranking.md` | This file |
| `docs/INDEX.md` | Updated with new spec, feature, and dev log entries |

---

## Ranking factor weights (final)

```python
GATE2_RANK_WEIGHTS = {
    "gate2_depth": 0.25,
    "gate2_edge":  0.25,
    "reward":      0.20,
    "volume":      0.15,
    "competition": 0.10,
    "age":         0.05,
}
```

Gate 2 signals (depth+edge) get 50% combined weight — they're the primary signal.
Market quality gets the other 50% as tiebreaker and watch-priority signal.

---

## Missing data policy

Unknown factors contribute 0 to rank_score. Each unknown emits an explanation line:

```
reward: UNKNOWN — no reward_config data (market may not participate in a reward program)
```

This prevents missing data from acting as positive evidence.

---

## New-market logic

Age factor = 1.0 if `age_hours < 48`, else 0.0. Hard threshold because the
operator action (label tape with `--regime new_market`) is binary.

Markets < 48h old are flagged in the output table (`New? = Y`) and the explanation
warns the operator to use `--regime new_market` during tape capture.

---

## Test count

14 tests in `tests/test_gate2_candidate_ranking.py`:
- Complete input scoring
- All-UNKNOWN missing-data case
- Missing data does not inflate rank_score
- New-market flag (< 48h)
- Mature market flag (>= 48h)
- New-market age_factor contribution to rank_score
- Unknown age (no created_at)
- Gate2 status codes (EXECUTABLE / NEAR / EDGE_ONLY / DEPTH_ONLY / NO_SIGNAL)
- Regime label written when present
- Regime UNKNOWN when not set
- Ranking: executable first
- Ranking: by rank_score for non-executable
- Empty list
- Integration: `score_and_rank_candidates` with market_meta

---

## Factors that remain unknown

| Factor | Reason | Operator action |
|--------|--------|----------------|
| volume_24h | Requires separate Gamma metadata call not in current live scan | Accept UNKNOWN; use --enrich in future |
| competition | Requires orderbook pass-through from live scan | Pass `orderbooks` dict to `score_and_rank_candidates()` when available |
| reward | Not all markets have reward programs | Accept UNKNOWN where absent |
| age | Some Gamma responses lack `created_at` | Accept UNKNOWN; check manually |
| regime | Not API-derivable | Set `--regime` during tape capture per SPEC-0014 |
