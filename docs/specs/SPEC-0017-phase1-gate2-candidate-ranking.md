# SPEC-0017: Phase 1 Gate 2 Candidate Ranking

**Status:** Accepted
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## 1. Purpose and scope

Define the canonical ranking contract for Gate 2 candidate markets — the markets
an operator selects for watchlist assignment before recording eligible tapes.

The current `scan-gate2-candidates` output ranks by depth+edge signals only.
This spec extends the ranking to include reward, volume, competition, and
new-market signals in an **explainable, operator-readable format** while
preserving existing Gate 2 pass criteria.

**In scope:**
- Ranking factors and their weights for Gate 2 candidate discovery
- Explainability contract (factor breakdown per candidate)
- Missing-data handling policy (UNKNOWN, never positive evidence)
- New-market and regime visibility in ranking output
- Acceptance criteria and tests

**Out of scope:**
- Gate 2 sweep pass criteria (unchanged; remain in `close_sweep_gate.py`)
- `market_maker_v0` market selection (uses `scorer.py` directly)
- Watch/record/tape-manifest workflow (unchanged; see SPEC-0014)
- Discord alerting, deploy scripts, Grafana, FastAPI

---

## 2. Ranking factors

All factors are normalized to [0, 1]. Missing data contributes **zero** —
it does NOT count as positive evidence.

| Factor | Weight | Source | UNKNOWN condition |
|--------|--------|--------|------------------|
| `gate2_depth` | 25% | CandidateResult.max_depth_{yes,no} | Never unknown (always from scan) |
| `gate2_edge` | 25% | CandidateResult.best_edge | BBO data unavailable for both legs |
| `reward` | 20% | reward_config.reward_rate | No reward_config or rate is zero |
| `volume` | 15% | market.volume_24h | No market metadata supplied |
| `competition` | 10% | orderbook bids (thin-bid count) | No orderbook supplied |
| `age` | 5% | market.created_at | No created_at in metadata |

**Sum of weights: 100%.**

### Factor definitions

**gate2_depth** (`weight: 0.25`):
```
depth_factor = min(min(depth_yes, depth_no) / max_size, 1.0)
```
Weaker leg determines the score. At depth = max_size (50 shares), factor = 1.0.

**gate2_edge** (`weight: 0.25`):
```
edge_factor = clamp((best_edge - (-0.10)) / 0.15, 0, 1)
```
Normalized over `[-0.10, +0.05]`. At `best_edge = -0.10` (10 cents above threshold) factor = 0;
at `best_edge = +0.05` (5 cent arb window) factor = 1. Uses sentinel detection to produce
UNKNOWN when no dual-leg BBO exists.

**reward** (`weight: 0.20`):
```
reward_factor = min(reward_rate * 365 / 3.0, 1.0)
```
Normalized to a maximum annual rate of 3.0 (300%). UNKNOWN when reward_config is absent.

**volume** (`weight: 0.15`):
```
volume_factor = min(volume_24h / 50_000, 1.0)
```
Normalized at $50k daily volume. UNKNOWN when volume_24h field is absent.

**competition** (`weight: 0.10`):
```
n_thin = count(bids where price * size < $50)
competition_factor = 1 / (n_thin + 1)
```
Thin bids proxy for low-quality market participants. High score = less competition.
UNKNOWN when orderbook is not supplied.

**age** (`weight: 0.05`):
```
age_factor = 1.0 if age_hours < 48 else 0.0
```
New markets (< 48h) receive a bonus because they exhibit distinct spread dynamics
(wider spreads, lower liquidity, higher reward APR volatility). This is a hard
threshold, not a decay, because the operator behavior change (use `--regime new_market`)
is binary. UNKNOWN when created_at is absent.

---

## 3. Gate 2 status codes

Every `Gate2RankScore` carries a `gate2_status` summary:

| Status | Condition | Meaning |
|--------|-----------|---------|
| `EXECUTABLE` | `executable_ticks > 0` | Simultaneous depth+edge seen — tape is eligible |
| `NEAR` | `edge_ok_ticks > 0` AND `depth_ok_ticks > 0` | Both seen, but not at same tick |
| `EDGE_ONLY` | `edge_ok_ticks > 0` only | Complement sum crossed threshold; depth insufficient |
| `DEPTH_ONLY` | `depth_ok_ticks > 0` only | Depth OK; sum_ask never below threshold |
| `NO_SIGNAL` | All counts = 0 | Neither condition met at this snapshot |

**EXECUTABLE is the only status that can advance to Gate 2 close.** All other
statuses indicate candidate watch priority, not tradability.

---

## 4. Ranking sort order

```python
rank_gate2_candidates(scores) → sorted by:
  1. executable_ticks DESC  (confirmed Gate 2 signal first)
  2. rank_score DESC        (composite attractiveness for watchlist selection)
  3. edge_ok_ticks DESC     (secondary signal)
  4. depth_ok_ticks DESC    (tertiary signal)
```

---

## 5. New-market policy

Markets less than 48 hours old receive `is_new_market = True` and `age_factor = 1.0`.
The explanation line reads:

```
age: NEW MARKET (20.0h old) — wider spreads, lower competition, and higher reward
volatility expected; label tape with --regime new_market
```

**Operator action required**: when a new market appears in top candidates, label any
resulting tape with `--regime new_market` during capture (see SPEC-0014 §4).

---

## 6. Missing-data policy

> "UNKNOWN means the operator does not know — it is NOT evidence of quality."

- Missing factors score **zero** on their weight contribution.
- The explanation line reads `FACTOR: UNKNOWN — <reason why data is absent>`.
- Operators can enrich rankings by supplying `market_meta`, `reward_configs`, and
  `orderbooks` to `score_and_rank_candidates()`, or by using `--enrich` on the
  live CLI to fetch optional metadata without changing default scan behavior.

---

## 7. CLI surface

```bash
# Default: Gate 2 signals + UNKNOWN for market quality factors
python -m polytool scan-gate2-candidates --all --top 20

# Full factor breakdown per candidate
python -m polytool scan-gate2-candidates --all --top 20 --explain

# Live scan with optional metadata enrichment to reduce UNKNOWN fields
python -m polytool scan-gate2-candidates --all --top 20 --explain --enrich

# Tape scan with factor breakdown
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --explain

# Emit ranked JSON artifact for make-session-pack consumption
python -m polytool scan-gate2-candidates --all --top 20 --ranked-json-out artifacts/watchlists/ranked.json

# Combine ranked JSON with exact-slug watchlist export
python -m polytool scan-gate2-candidates --all --top 20 \
  --watchlist-out artifacts/watchlists/gate2_top20.txt \
  --ranked-json-out artifacts/watchlists/gate2_top20_ranked.json
```

### `--ranked-json-out PATH`

Writes a machine-readable JSON artifact (`gate2_ranked_scan_v1`) alongside the
human table. The file contains every field from `Gate2RankScore` — slug,
gate2_status, rank_score, executable/edge/depth ticks, best_edge, depth_yes/no,
regime/regime_source, is_new_market, age_hours, explanation lines — for each
shown candidate.

This artifact is the canonical input for `make-session-pack --ranked-json PATH`.
It lets the operator move from scan output to a disciplined session pack without
hand-copying slugs or losing the advisory context produced by scoring.

### Output columns

```
Market                                       | Status | Score | Exec | BestEdge  | MaxDepth YES/NO  | Age      | Regime       | RegSrc
```

- **Status**: gate2_status abbreviation (EXEC/NEAR/EDGE/DEPTH/NONE)
- **Score**: rank_score (0.000–1.000)
- **Exec**: executable_ticks count
- **BestEdge**: best_edge value (+ = arb existed, N/A = no BBO)
- **MaxDepth YES/NO**: peak best-ask sizes per leg
- **Age**: `NEW <Nh>` when age metadata says `< 48h`, `<Nh>` when mature, `UNKNOWN` when age metadata is absent
- **Regime**: derived regime when classifier signal is strong; otherwise operator label fallback; otherwise `UNKNOWN`
- **RegSrc**: `derived`, `operator`, or `UNKNOWN`

With `--explain`, each row is followed by its full factor breakdown, including
regime provenance (`source`, `derived`, `operator`) on the regime line.

---

## 8. Operator guidance: using the output during catalyst windows

1. Run `scan-gate2-candidates --all --top 20 --explain` before and during catalyst events
   (game start, vote close, news breaks).
2. Focus on markets with `Status = NEAR` or `EDGE_ONLY` — these are closest to becoming
   `EXECUTABLE`.
3. Check the `Age` column: `NEW <Nh>` rows indicate markets younger than 48 hours
   and should be labeled `--regime new_market` during tape capture if preserving
   early-market behavior.
4. `Score` is a watchlist-priority signal — high score means the market has good depth,
   reward, and volume. It does NOT predict whether a dislocation will occur.
5. Markets with many `UNKNOWN` factors are not penalized but are also not boosted.
   Enrich the data (supply market metadata or use live `--enrich`) to get a
   more meaningful rank_score.

---

## 9. Factors that remain unknown due to data limits

| Factor | Why it may be unknown | How to resolve |
|--------|----------------------|----------------|
| reward | Market has no reward program, or Gamma API returns no rate | Accept UNKNOWN; not all markets pay rewards |
| volume_24h | Gamma metadata may not include a 24h-volume field for the market | Use live `--enrich`; if Gamma still omits a 24h field, remain `UNKNOWN` |
| competition | Requires orderbook; live scan does not pass books to scorer by default | Pass orderbook via `score_and_rank_candidates(orderbooks=...)` or use live `--enrich` |
| age | Metadata has no `created_at` / `age_hours` field | Use live `--enrich`; if created-time metadata is still absent, remain `UNKNOWN` |
| regime | Slug/question/tag/category metadata is too weak to classify, and no operator label is supplied | Accept UNKNOWN; operator label is fallback only |

---

## 10. Acceptance criteria

1. `Gate2RankScore.explanation` always contains one line per factor (reward, volume,
   competition, age, regime) plus a `GATE2:` summary header.
2. `UNKNOWN` appears in explanation for each factor where data is absent.
3. `is_new_market = True` when `age_hours < 48`; False when `>= 48`; None when unknown.
4. Regime output uses `classify_market_regime()` when metadata provides a clear signal
   and only falls back to operator labels when the classifier is weak.
5. `rank_score` for a market with all-UNKNOWN market quality factors equals
   `gate2_depth_factor * 0.25 + gate2_edge_factor * 0.25` (only Gate 2 signals contribute).
6. `rank_gate2_candidates` places `executable_ticks > 0` markets first, regardless of
   `rank_score` of other candidates.
7. `score_and_rank_candidates(results)` wraps `CandidateResult` list and returns
   `list[Gate2RankScore]` without error when all market metadata dicts are None.
8. All tests in `tests/test_gate2_candidate_ranking.py` pass.
9. All tests in `tests/test_market_selection.py` still pass.
10. `scan-gate2-candidates --enrich` is optional and live-only; omitting it preserves
    current default behavior.
11. If any enrichment fetch fails, ranking remains non-fatal and the affected
    factors stay `UNKNOWN`.
12. `scan-gate2-candidates --ranked-json-out PATH` writes a valid
    `gate2_ranked_scan_v1` JSON file with `schema_version`, `scan_mode`,
    `total_candidates`, `shown_candidates`, and a `candidates` array where
    each entry includes `rank`, `slug`, `gate2_status`, `rank_score`, and
    `explanation`. The file is machine-readable by
    `make-session-pack --ranked-json PATH`.

---

## References

- `packages/polymarket/market_selection/scorer.py` — `Gate2RankScore`, `score_gate2_candidate`, `rank_gate2_candidates`
- `tools/cli/scan_gate2_candidates.py` — `score_and_rank_candidates`, `print_ranked_table`
- `tests/test_gate2_candidate_ranking.py` — acceptance tests
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — market selection policy
- `docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md` — Gap matrix, Requirement 6
- `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` — tape capture workflow
