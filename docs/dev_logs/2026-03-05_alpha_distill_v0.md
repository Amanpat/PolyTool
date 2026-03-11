# Dev Log: Alpha-Distill v0 (2026-03-05)

## Summary

Implemented `polytool alpha-distill` — a research-only command that reads
wallet-scan leaderboard outputs and per-user `segment_analysis.json` artifacts,
aggregates segment metrics cross-user, and emits ranked edge hypothesis candidates
as structured JSON. No LLM calls. No black-box scores. No strategy execution.

---

## Files Touched

| File | Change |
|---|---|
| `tools/cli/alpha_distill.py` | New — CLI entrypoint + distillation logic |
| `polytool/__main__.py` | Added `alpha-distill` command routing |
| `tests/test_alpha_distill.py` | New — 27 unit tests (all offline) |
| `docs/specs/SPEC-alpha-distill-v0.md` | New — spec |
| `docs/dev_logs/2026-03-05_alpha_distill_v0.md` | This file |

---

## Design Choices

### No raw position data required

Distillation reads only finalized `segment_analysis.json` files — not raw
position records. This keeps it fast (no ClickHouse queries) and composable
(any wallet-scan run is immediately distillable).

### `_SegmentAccumulator` class

Each `(dimension, key)` pair gets one accumulator that re-weights per-user
finalized bucket metrics into a cross-user aggregate. The weighted-mean
approach (count-weighted for CLV, notional-weight-weighted for notional metrics)
is statistically correct and matches the methodology in `batch_run.py`.

### Ranking score formula

```
score = users_contributing × 1000
      + min(total_count, 500)
      + max(0, net_clv_after_fee_adj) × 500
```

Persistence (multi-user) dominates by design — 1000× weight vs count's maximum
500. A segment appearing in 2 users with 10 positions each outranks a segment
in 1 user with 400 positions. This is intentionally conservative: reproducibility
across wallets is stronger evidence than a single large position set.

The count cap at 500 prevents a single very large user from dominating the
count contribution indefinitely.

### Conservative fee adjustment (default 2 pp)

Subtracting 2 percentage points from CLV% is a pessimistic friction estimate.
This guards against reporting edge that disappears after realistic transaction
costs. The flag `fee_estimate_only` is always set because fees are estimated
from the quadratic curve (not actual per-trade fee records).

### Segment key filtering

The `unknown` segment key is excluded from all axes (it's a data quality
residual, not a meaningful segment). The `total` key (appears in `by_market_type`)
is also excluded for the same reason.

### Mechanism hints

Each dimension has a static research-quality mechanism hint explaining what
a positive signal in that dimension could mean. This is intentionally hedged
("may indicate", "may reflect") — not a claim of alpha or a trading signal.

### Falsification gates

Every candidate includes:
- `next_test`: exact step to continue validation
- `stop_condition`: concrete criteria to discard the hypothesis

These follow the Strategy Playbook requirement that every hypothesis includes
a falsification method.

---

## Tests

27 tests in `tests/test_alpha_distill.py`, all offline:

- `TestLoadWalletScanRun`: loads leaderboard + jsonl, raises on missing files
- `TestLoadUserSegmentAnalysis`: reads inner dict, handles missing/corrupt files
- `TestSegmentAccumulator`: single user, two-user weighted CLV, zero-count skip,
  win_rate aggregation, notional-weighted CLV aggregation
- `TestFrictionRiskFlags`: all 4 flag conditions
- `TestScoreAccumulator`: persistence > count, positive CLV > negative CLV
- `TestDistill` (integration): required fields, min_sample filter, failed users
  excluded, rank ordering by users_contributing, net_clv_after_fee_adj,
  unknown key exclusion, summary fields, contiguous rank starting at 1

One test bug fixed during development: `_acc(count=5, users=2)` → total=10
which equals min_sample=10, not less. Fixed to `count=3`.

---

## Not Implemented (v0 scope)

- Cross-segment interaction (e.g., `nfl AND deep_underdog`)
- `by_market_slug` dimension (too user-specific, low cross-user signal)
- Time-series analysis across multiple scan dates
- Threshold-based automatic candidate promotion/demotion
- HTML report generation
