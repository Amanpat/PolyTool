# Feature: Alpha-Distill v0

**Status**: Implemented (2026-03-05)
**Spec**: [docs/specs/SPEC-alpha-distill-v0.md](../specs/SPEC-alpha-distill-v0.md)
**CLI command**: `python -m polytool alpha-distill`

---

## What it does

`alpha-distill` reads the output of a `wallet-scan` run plus each user's
`segment_analysis.json` artifact, aggregates segment metrics **cross-user**, and
emits a ranked JSON file of **edge hypothesis candidates**.

No LLM. No black-box scores. No order placement. All outputs are explainable,
falsifiable, and research-only.

Every candidate carries:
- Cross-user persistence metrics (how many distinct wallets show the same pattern)
- Sample size gates (minimum position count to form a candidate)
- Friction risk flags (fee estimate quality, sparse CLV data, single-user-only)
- A `next_test` field (exact next validation step)
- A `stop_condition` field (when to discard the hypothesis)

---

## CLI usage

```bash
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/2026-03-05/<run_id> \
  [--out alpha_candidates.json] \
  [--min-sample 30] \
  [--fee-adj 0.02]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--wallet-scan-run` | required | Path to a `wallet-scan` run root directory |
| `--out` | `<run-root>/alpha_candidates.json` | Output path |
| `--min-sample` | 30 | Min total positions across users to form a candidate |
| `--fee-adj` | 0.02 | Conservative fee adjustment subtracted from CLV% (2 pp) |

---

## Inputs consumed

- `<wallet-scan-run>/leaderboard.json` — lists succeeded users and their run_roots
- `<wallet-scan-run>/per_user_results.jsonl` — per-user status
- For each succeeded user: `<scan-run-root>/segment_analysis.json`

`segment_analysis.json` is emitted by every `polytool scan` run. It contains
pre-computed breakdowns by entry price tier, market type, league, sport, and
category with win rates, CLV%, beat-close rates, and PnL.

---

## Segment dimensions analyzed

| Dimension | Key examples |
|-----------|-------------|
| `entry_price_tier` | `deep_underdog`, `underdog`, `coinflip`, `favorite` |
| `market_type` | `moneyline`, `spread` |
| `league` | `nfl`, `nba`, `nhl`, `epl` |
| `sport` | `basketball`, `american_football`, `soccer` |
| `category` | Polymarket category field verbatim |

The `unknown` key is excluded from all dimensions (data quality residual).

---

## Ranking philosophy

Score formula (higher = better):

```
score = users_contributing × 1000
      + min(total_count, 500)
      + max(0, net_clv_after_fee_adj) × 500
```

**Multi-user persistence dominates** (~1000× weight over count) by design. A pattern
appearing across 3 distinct wallets is much stronger evidence than 3× the positions
in a single wallet. This is an intentionally conservative prior.

The count cap at 500 prevents any single large user from dominating indefinitely.

---

## Candidate JSON schema summary

Output file: `alpha_candidates.json`

```json
{
  "schema_version": "alpha_distill_v0",
  "run_id": "...",
  "created_at": "...",
  "parameters": { "min_sample_size": 30, "conservative_fee_adj": 0.02, ... },
  "summary": { "total_users_in_leaderboard": 5, "candidates_generated": 7, ... },
  "candidates": [
    {
      "candidate_id": "entry_price_tier__deep_underdog__rank001",
      "rank": 1,
      "label": "Entry price tier edge (entry_price_tier=deep_underdog)",
      "mechanism_hint": "...",
      "evidence_refs": [ { "user": "alice", "count": 22, ... } ],
      "sample_size": 45,
      "measured_edge": {
        "win_rate": 0.58,
        "avg_clv_pct": 0.04,
        "notional_weighted_avg_clv_pct": 0.05,
        "users_contributing": 3,
        "net_clv_after_fee_adj": 0.03,
        ...
      },
      "friction_risk_flags": ["fee_estimate_only"],
      "next_test": "With N=45 across 3 users, verify notional_weighted_avg_clv_pct persists...",
      "stop_condition": "Discard if beat_close_rate drops below 0.50 with total_count >= 90..."
    }
  ]
}
```

---

## Friction risk flags

| Flag | Condition |
|------|-----------|
| `fee_estimate_only` | Always present in v0 — fees are estimated, not actual per-trade |
| `single_user_only` | Only 1 user contributes to this segment |
| `clv_data_sparse` | CLV-covered positions < 30% of total |
| `small_sample` | Below `min_sample` (defensive; should not appear in candidates) |

---

## Limitations (v0)

- No cross-segment interaction analysis (e.g., `league=nfl AND entry_price_tier=deep_underdog`)
- `by_market_slug` dimension excluded (too user-specific)
- Sparse CLV data when scan ran without `--compute-clv`
- All fees estimated; `fee_estimate_only` always present
- No time-series analysis across scan dates

---

## Typical research loop

```
wallets.txt
  → python -m polytool wallet-scan --input wallets.txt
  → artifacts/research/wallet_scan/<date>/<run_id>/
      leaderboard.json
      per_user_results.jsonl
  → python -m polytool alpha-distill --wallet-scan-run <run_id_path>
  → alpha_candidates.json   ← ranked edge hypothesis candidates
  → manual review / hypothesis validation
```
