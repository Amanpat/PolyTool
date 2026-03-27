# Phase 1B Candidate Discovery Upgrade

**Date:** 2026-03-27
**Quick task:** quick-032
**Author:** Claude Code

## Summary

Replaced the flat `auto_pick_many` call in `quickrun --list-candidates` with a
scored, ranked shortlist drawn from a larger market pool (up to 200 Gamma markets).
Added bucket inference, shortage-aware scoring, one-sided market rejection, and a
transparent `rank_reason` string per candidate.

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/candidate_discovery.py` | NEW — CandidateDiscovery module |
| `tests/test_simtrader_candidate_discovery.py` | NEW — 27 offline tests |
| `tools/cli/simtrader.py` | MODIFIED — list-candidates block replaced |
| `tests/test_simtrader_activeness_probe.py` | MODIFIED — 2 tests updated for new format |
| `tests/test_simtrader_quickrun.py` | MODIFIED — 5 tests updated for new format |

## Old Behavior

`quickrun --list-candidates N` called `picker.auto_pick_many(n=N, max_candidates=N)` directly.
This fetched a single Gamma page (`limit=N`, typically 20) in whatever order the API returned,
with no bucket awareness, no shortage boosting, and no one-sided market filtering.

Output showed only slug, question, YES/NO depth:
```
[candidate 1] slug     : some-market
[candidate 1] question : Will this happen?
[candidate 1] YES depth: 45.0
[candidate 1] NO depth : 38.0
```

With a default of 20 markets examined, sports/crypto/politics markets (the high-shortage
buckets) were rarely first in the Gamma feed and would often not appear in the shortlist.

## New Behavior

`quickrun --list-candidates N` creates a `CandidateDiscovery` instance and calls
`.rank(n=N, pool_size=200)`. The discovery pipeline:

1. **Pool expansion:** Fetches up to `pool_size` (default 200, capped at 200) raw market
   dicts from Gamma via paginated `fetch_markets_page` calls (100 per page, 2 pages max).

2. **Resolution + validation:** Calls `auto_pick_many(n=pool_size, ...)` to get the
   validated, resolved market list (YES/NO token IDs, orderbook check).

3. **Bucket inference:** Each market is classified using:
   - `classify_market_regime()` from `regime_policy.py` → politics, sports, new_market
   - Near-resolution heuristic: `end_date_iso` within 72h of now(UTC) → near_resolution
   - Crypto keyword match on slug+question (btc/eth/sol/crypto/bitcoin/ethereum/solana) → crypto
   - Fallback: other

4. **Scoring:** Each candidate receives a composite score in [0.0, 1.0]:
   - `shortage_boost = clamp(shortage[bucket] / 15.0, 0, 1)` — weight 0.40
   - `depth_score = min(avg_depth_total, 200) / 200` — weight 0.30
   - `probe_score = 1.0 (active) | 0.0 (inactive) | 0.5 (no probe)` — weight 0.20
   - `spread_score = clamp((ask - bid) / 0.15, 0, 1)` — weight 0.10

5. **Rejection:** Markets with `one_sided_book` or `empty_book` on either leg score 0.0
   and are excluded from the shortlist entirely.

6. **Sorting:** Remaining candidates sorted descending by score; top N returned.

New output format:
```
[candidate 1] slug     : will-bills-win-2026
[candidate 1] question : Will the Bills win the Super Bowl?
[candidate 1] bucket   : sports
[candidate 1] score    : 0.87
[candidate 1] why      : bucket=sports shortage=15 score=0.87 depth=142 probe=active
[candidate 1] depth    : YES=142.0  NO=138.0
[candidate 1] probe    : 2/2 active, 18 updates
Listed 1 candidates.
```

## Ranking Factors and Weights

| Factor | Weight | Formula |
|--------|--------|---------|
| shortage_boost | 0.40 | shortage[bucket] / 15.0, clamped 0..1 |
| depth_score | 0.30 | min(avg_depth, 200) / 200 |
| probe_score | 0.20 | 1.0 active / 0.0 inactive / 0.5 no probe |
| spread_score | 0.10 | (ask - bid) / 0.15, clamped 0..1 |

## Shortage Constants (Phase 1B defaults, hardcoded)

```python
_DEFAULT_SHORTAGE = {
    "sports": 15,
    "politics": 9,
    "crypto": 10,
    "new_market": 5,
    "near_resolution": 1,
    "other": 0,
}
```

These are the Phase 1B campaign values as of 2026-03-27.
**Update these after each capture batch using `python tools/gates/capture_status.py`.**
The constants live in two places: `candidate_discovery.py` (module default) and
`tools/cli/simtrader.py` (CLI override, labeled "Phase 1B campaign defaults").

## Pool Size Calculation

`pool_size = min(getattr(args, "max_candidates", 20) * 10, 200)`

- Default `--max-candidates=20` → pool_size=200
- `--max-candidates=5` → pool_size=50
- Hard cap at 200 to avoid excessive Gamma API calls

No new CLI flags were added. Operators can influence pool_size via the existing
`--max-candidates` flag.

## Commands Run

```bash
# RED phase (Task 1) — tests written first
python -m pytest tests/test_simtrader_candidate_discovery.py -x -q
# FAILED: 27 collected, 27 errors (module not yet created)

# GREEN phase (Task 1) — module implemented
python -m pytest tests/test_simtrader_candidate_discovery.py -x -q
# 27 passed in 0.12s

# CLI verification
python -m polytool simtrader quickrun --help
# exit 0

# Full regression (Task 2)
python -m pytest tests/ -q --tb=short
# 2712 passed, 0 failed, 25 warnings
```

## Test Counts

| File | Tests |
|------|-------|
| `tests/test_simtrader_candidate_discovery.py` (new) | 27 |
| Existing tests updated for new output format | 6 |
| Total suite | 2712 passed |

## Open Questions

1. **Auto-refresh shortage from corpus_audit output:** Today the shortage constants are
   hardcoded. After each Gold capture session, the operator should manually update the
   constants in `candidate_discovery.py` and `simtrader.py`. A future improvement could
   parse `artifacts/corpus_audit/shortage_report.md` or `capture_status.py --json` output
   and inject the values automatically.

2. **Weight tuning:** The weights (0.40/0.30/0.20/0.10) were chosen to prioritize shortage
   signal above depth and probe activity. After the first capture session using this tool,
   review whether the weights produce the right bucket distribution in shortlists. Crypto
   and sports candidates should surface reliably when present in the pool.

3. **Pool size cap:** Hard cap of 200 was chosen to avoid excessive API calls. If the
   Gamma API rate limits become an issue, reduce to 100. If the pool consistently returns
   < 50 valid candidates, increase the cap in `_MAX_POOL_SIZE`.
