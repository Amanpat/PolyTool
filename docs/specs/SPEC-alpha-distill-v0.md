# SPEC-alpha-distill-v0: Segment Edge Distillation (No LLM)

## Status

Draft — implemented in `tools/cli/alpha_distill.py` (2026-03-05).

---

## Purpose

`alpha-distill` reads the outputs of `wallet-scan` (leaderboard + per_user_results)
and each user's `segment_analysis.json` artifacts, then emits a structured JSON
file of ranked edge hypothesis candidates. No LLM. No trading signals. No execution.

All outputs are explainable and falsifiable: every candidate includes sample size
gates, stop conditions, and friction risk flags.

---

## CLI Interface

```
python -m polytool alpha-distill \
  --wallet-scan-run <path> \
  [--out alpha_candidates.json] \
  [--min-sample 30] \
  [--fee-adj 0.02] \
  [--run-id <uuid>]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--wallet-scan-run` | (required) | Path to a wallet-scan run root directory |
| `--out` | `<run-root>/alpha_candidates.json` | Output path |
| `--min-sample` | 30 | Minimum positions (total across users) to form a candidate |
| `--fee-adj` | 0.02 | Conservative fee adjustment subtracted from CLV% |
| `--run-id` | random uuid4 | Unique run ID |

---

## Inputs

- `<wallet-scan-run>/leaderboard.json` — lists succeeded users and their run_roots
- `<wallet-scan-run>/per_user_results.jsonl` — per-user status and metadata
- For each succeeded user: `<scan-run-root>/segment_analysis.json`

`segment_analysis.json` is written by every `polytool scan` run and contains
`by_entry_price_tier`, `by_market_type`, `by_league`, `by_sport`, `by_category`
buckets with position counts, win rates, CLV%, beat-close rates, and PnL.

---

## Algorithm

1. Load wallet-scan `leaderboard.json` + `per_user_results.jsonl`.
2. For each succeeded user, load their `segment_analysis.json`.
3. For each segment dimension × key (5 dimensions × N keys per user):
   - Accumulate cross-user aggregate metrics using notional-weight-aware sums.
   - Track which users contribute to each (dimension, key) pair.
4. Filter: skip "unknown" segment keys; skip segments with `total_count < min_sample`.
5. Score each remaining segment (see Ranking section).
6. Build and emit ranked candidates.

---

## Segment Dimensions

| Dimension | segment_analysis key | Examples |
|---|---|---|
| `entry_price_tier` | `by_entry_price_tier` | `deep_underdog`, `underdog`, `coinflip`, `favorite` |
| `market_type` | `by_market_type` | `moneyline`, `spread` |
| `league` | `by_league` | `nfl`, `nba`, `nhl`, `epl` |
| `sport` | `by_sport` | `basketball`, `american_football`, `soccer` |
| `category` | `by_category` | Polymarket `category` field verbatim |

The `unknown` key is excluded from all dimensions (data quality residual).

---

## Aggregation

For each (dimension, key) pair across users:

| Metric | Aggregation method |
|---|---|
| `total_count` | Sum across users |
| `total_pnl_net` | Sum across users |
| `win_rate` | Weighted mean by resolved-count denominator |
| `avg_clv_pct` | Weighted mean by `avg_clv_pct_count_used` |
| `beat_close_rate` | Weighted mean by `beat_close_rate_count_used` |
| `notional_weighted_avg_clv_pct` | Weighted mean by `notional_weighted_avg_clv_pct_weight_used` |
| `notional_weighted_beat_close_rate` | Weighted mean by `notional_weighted_beat_close_rate_weight_used` |

All re-aggregation is a weighted mean over per-user finalized bucket values — no raw
position data is required beyond what `segment_analysis.json` already contains.

---

## Ranking

Score (higher = better):

```
score = users_contributing × 1000
      + min(total_count, 500)
      + max(0, net_clv_after_fee_adj) × 500
```

where `net_clv_after_fee_adj = primary_clv - conservative_fee_adj`
and `primary_clv = notional_weighted_avg_clv_pct` (or `avg_clv_pct` if null).

Priority rationale:
- **Persistence** (multi-user, ~1000x weight): the strongest signal. A pattern
  appearing in 3 wallets is much stronger evidence than 3× the positions in 1 wallet.
- **Count** (secondary): more positions = more trustworthy aggregate.
- **Edge** (tiebreaker): positive net-of-fees CLV nudges equivalent-persistence candidates.

---

## alpha_candidates.json Schema

```json
{
  "schema_version": "alpha_distill_v0",
  "run_id": "<uuid>",
  "created_at": "<ISO-8601 UTC>",
  "wallet_scan_run_root": "<path>",
  "parameters": {
    "min_sample_size": 30,
    "conservative_fee_adj": 0.02,
    "min_users_persistence": 2
  },
  "summary": {
    "total_users_in_leaderboard": 5,
    "total_users_analyzed": 4,
    "users_with_segment_data": 4,
    "total_segments_evaluated": 20,
    "candidates_generated": 7
  },
  "candidates": [
    {
      "candidate_id": "entry_price_tier__deep_underdog__rank001",
      "rank": 1,
      "label": "Entry price tier edge (entry_price_tier=deep_underdog)",
      "mechanism_hint": "Traders entering at this price tier...",
      "evidence_refs": [
        {
          "user": "alice",
          "run_root": "artifacts/dossiers/users/alice/.../",
          "segment_file": "artifacts/.../segment_analysis.json",
          "dimension": "entry_price_tier",
          "key": "deep_underdog",
          "count": 22
        }
      ],
      "sample_size": 45,
      "required_min_sample": 30,
      "measured_edge": {
        "total_count": 45,
        "total_pnl_net": 8.4,
        "win_rate": 0.58,
        "win_rate_denominator": 40,
        "avg_clv_pct": 0.04,
        "avg_clv_pct_count_used": 30,
        "beat_close_rate": 0.63,
        "beat_close_rate_count_used": 30,
        "notional_weighted_avg_clv_pct": 0.05,
        "notional_weighted_avg_clv_pct_weight_used": 200.0,
        "notional_weighted_beat_close_rate": 0.62,
        "notional_weighted_beat_close_rate_weight_used": 200.0,
        "users_contributing": 3,
        "conservative_fee_adj": 0.02,
        "net_clv_after_fee_adj": 0.03
      },
      "friction_risk_flags": ["fee_estimate_only"],
      "next_test": "With N=45 across 3 user(s), verify notional_weighted_avg_clv_pct persists...",
      "stop_condition": "Discard if beat_close_rate drops below 0.50 with total_count >= 90..."
    }
  ]
}
```

---

## Candidate Fields

| Field | Type | Description |
|---|---|---|
| `candidate_id` | string | `{dimension}__{key}__rank{N:03d}` |
| `rank` | int | 1-based rank by score |
| `label` | string | Human-readable segment description |
| `mechanism_hint` | string | Research-quality text on possible edge source |
| `evidence_refs` | object[] | Per-user contributing evidence (user, run_root, segment_file, count) |
| `sample_size` | int | `total_count` across all users |
| `required_min_sample` | int | Configured `--min-sample` threshold |
| `measured_edge` | object | Aggregate metrics (CLV, beat-close, win rate, PnL, fee adj) |
| `friction_risk_flags` | string[] | Risk flags (see below) |
| `next_test` | string | Exact next verification step |
| `stop_condition` | string | When to discard this hypothesis |

---

## Friction Risk Flags

| Flag | Condition |
|---|---|
| `fee_estimate_only` | Always set in v0 — fees are estimated, not actual per-trade rates |
| `small_sample` | `total_count < min_sample` (should not appear in candidates, but included defensively) |
| `single_user_only` | Only 1 user contributes to this segment |
| `clv_data_sparse` | `clv_count_used / total_count < 0.30` |

---

## Limitations (v0)

- No cross-segment interaction analysis (e.g., `league=nfl AND entry_price_tier=deep_underdog`)
- `by_market_slug` dimension is not included (too user-specific)
- Segment data may be sparse if scan was run without `--compute-clv`
- All fees are estimated; `fee_estimate_only` flag always present
- No time-series analysis (no trend over scan dates)

---

## Files

| Path | Role |
|---|---|
| `tools/cli/alpha_distill.py` | CLI entrypoint + distillation logic |
| `polytool/__main__.py` | Command registration (`alpha-distill`) |
| `tests/test_alpha_distill.py` | Unit tests |
| `docs/specs/SPEC-alpha-distill-v0.md` | This spec |
