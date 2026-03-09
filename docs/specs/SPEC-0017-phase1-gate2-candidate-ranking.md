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
  `orderbooks` to `score_and_rank_candidates()`, or by using `--enrich` on the CLI
  when a future version adds live metadata fetch.

---

## 7. CLI surface

```bash
# Default: Gate 2 signals + UNKNOWN for market quality factors
python -m polytool scan-gate2-candidates --all --top 20

# Full factor breakdown per candidate
python -m polytool scan-gate2-candidates --all --top 20 --explain

# Tape scan with factor breakdown
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --explain
```

### Output columns

```
Market                                       | Status | Score | Exec | BestEdge  | MaxDepth YES/NO  | New? | Regime
```

- **Status**: gate2_status abbreviation (EXEC/NEAR/EDGE/DEPTH/NONE)
- **Score**: rank_score (0.000–1.000)
- **Exec**: executable_ticks count
- **BestEdge**: best_edge value (+ = arb existed, N/A = no BBO)
- **MaxDepth YES/NO**: peak best-ask sizes per leg
- **New?**: Y (new market), N (mature), ? (unknown)
- **Regime**: labeled regime or `?`

With `--explain`, each row is followed by its full factor breakdown.

---

## 8. Operator guidance: using the output during catalyst windows

1. Run `scan-gate2-candidates --all --top 20 --explain` before and during catalyst events
   (game start, vote close, news breaks).
2. Focus on markets with `Status = NEAR` or `EDGE_ONLY` — these are closest to becoming
   `EXECUTABLE`.
3. Check `New?` column: new markets (Y) should be labeled `--regime new_market` during
   tape capture and monitored closely for early dislocation.
4. `Score` is a watchlist-priority signal — high score means the market has good depth,
   reward, and volume. It does NOT predict whether a dislocation will occur.
5. Markets with many `UNKNOWN` factors are not penalized but are also not boosted.
   Enrich the data (supply market metadata) to get a meaningful rank_score.

---

## 9. Factors that remain unknown due to data limits

| Factor | Why it may be unknown | How to resolve |
|--------|----------------------|----------------|
| reward | Market has no reward program, or Gamma API returns no rate | Accept UNKNOWN; not all markets pay rewards |
| volume_24h | Not included in live scan metadata (requires separate Gamma call) | Use `--enrich` flag (future enhancement) |
| competition | Requires orderbook; live scan does not pass books to scorer by default | Pass orderbook via `score_and_rank_candidates(orderbooks=...)` |
| age | Gamma does not return `created_at` for some markets | Accept UNKNOWN; check manually if market appears new |
| regime | Not derivable from API data alone | Set during tape capture with `--regime` flag |

---

## 10. Acceptance criteria

1. `Gate2RankScore.explanation` always contains one line per factor (reward, volume,
   competition, age, regime) plus a `GATE2:` summary header.
2. `UNKNOWN` appears in explanation for each factor where data is absent.
3. `is_new_market = True` when `age_hours < 48`; False when `>= 48`; None when unknown.
4. `rank_score` for a market with all-UNKNOWN market quality factors equals
   `gate2_depth_factor * 0.25 + gate2_edge_factor * 0.25` (only Gate 2 signals contribute).
5. `rank_gate2_candidates` places `executable_ticks > 0` markets first, regardless of
   `rank_score` of other candidates.
6. `score_and_rank_candidates(results)` wraps `CandidateResult` list and returns
   `list[Gate2RankScore]` without error when all market metadata dicts are None.
7. All tests in `tests/test_gate2_candidate_ranking.py` pass.
8. All tests in `tests/test_market_selection.py` still pass.

---

## References

- `packages/polymarket/market_selection/scorer.py` — `Gate2RankScore`, `score_gate2_candidate`, `rank_gate2_candidates`
- `tools/cli/scan_gate2_candidates.py` — `score_and_rank_candidates`, `print_ranked_table`
- `tests/test_gate2_candidate_ranking.py` — acceptance tests
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — market selection policy
- `docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md` — Gap matrix, Requirement 6
- `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` — tape capture workflow
