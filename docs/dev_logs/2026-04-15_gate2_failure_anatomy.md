# Gate 2 Failure Anatomy -- Decision-Grade Analysis

**Date:** 2026-04-15
**Task:** quick-260415-owc
**Author:** Claude Code (executor)

---

## Summary

The 50-tape Gate 2 corpus (benchmark_v1 manifest) was partitioned into three
structurally distinct classes using per-tape `sweep_summary.json` aggregate data
(fill counts, order counts, per-scenario PnL):

- **9 structural-zero-fill** (Silver tapes, all near_resolution bucket): no L2
  book data; fill engine cannot execute; zero fills and zero PnL across all
  scenarios regardless of spread parameter.
- **34 executable-negative-or-flat** (Shadow/Gold tapes): fills were generated but
  best-case PnL across all 5 spread scenarios was <= $0.  Includes politics (10),
  sports (15), near_resolution (1), new_market (5), and crypto (3) tapes.
- **7 executable-positive** (Shadow crypto tapes, all crypto bucket): fills
  generated and best-case PnL > $0 in at least one scenario.

The headline "7/50 = 14% FAIL" conflates two fundamentally different failure modes.
The crypto bucket alone achieves 7/10 = 70%, exactly the Gate 2 pass threshold.
This anatomy document provides the evidence base for the operator's path-forward
decision.

---

## Partition Table

| Partition | Count | Buckets | Total Fills (all scenarios) | Best PnL Range |
|---|---|---|---|---|
| structural-zero-fill | 9 | near_resolution=9 | 0 | [0.00, 0.00] |
| executable-negative-or-flat | 34 | crypto=3, near_resolution=1, new_market=5, politics=10, sports=15 | 42,247 | [-492.34, 0.00] |
| executable-positive | 7 | crypto=7 | 30,892 | [4.67, 297.25] |

---

## Partition Details

### structural-zero-fill (9 tapes)

**Why:** Silver tapes contain only `price_2min_guide` events which carry historical
price candles but no L2 order-book data.  The SimTrader `L2Book.apply()` method
ignores these events, so the book never initializes.  The BrokerSim fill engine
rejects all order submissions with `book_not_initialized`, producing zero fills and
zero PnL across every spread scenario.  This is a data-tier incompatibility, not
a strategy failure.  These tapes cannot contribute positive PnL under any parameter
setting until Gold-tier re-capture is performed.

| Market Slug | Bucket | Fills | Orders | Scenarios w/ Trades | Best PnL | Worst PnL |
|---|---|---|---|---|---|---|
| will-a-friend-of-dorothy-win-best-live-action-short-fil... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-arkansas-be-a-number-1-seed-in-the-2026-ncaa-mens-... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-alabama-be-a-number-1-seed-in-the-2026-ncaa-mens-b... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-armed-only-with-a-camera-the-life-and-death-of-bre... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-arco-win-best-animated-feature-film-at-the-98th-ac... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-arizona-be-a-number-1-seed-in-the-2026-ncaa-mens-b... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-amy-madigan-win-best-supporting-actress-at-the-98t... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-a-minecraft-movie-be-the-2025-film-with-the-highes... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |
| will-all-the-empty-rooms-win-best-documentary-short-fil... | near_resolution | 0 | 0 | 0 | 0.00 | 0.00 |

All 9 Silver tapes are near_resolution Academy Awards / NCAA seed prediction
markets captured via the pmxt + Jon-Becker + polymarket-apis reconstruction
pipeline.  They are correctly excluded from any Gate 2 pass count.

---

### executable-negative-or-flat (34 tapes)

**Why:** These Shadow/Gold tapes generated real fills (total 42,247 across all
scenarios) but the market-maker strategy could not extract positive spread capture.
Politics and sports markets at extreme probabilities (near 0 or 1) produce very
wide natural spreads; the strategy's logit A-S model quotes inside the natural
spread but the low trade frequency means adverse inventory accumulation exceeds
spread revenue.

Tapes showing $0 best PnL are **break-even-at-best** (fee costs exactly offset
gross spread capture or no profitable scenario exists among the 5 tested).  Tapes
showing negative best PnL are **net losers at every spread setting tested**.

Key examples:
- `will-a-different-combination-of-cand...` (politics): 209 fills, 3 orders,
  0 scenarios with trades, $0 best PnL -- extremely low-activity market
- `fif-col-fra-2026-03-29-draw` (sports): 1,271 fills across all scenarios but
  $0 best PnL -- high fill count but spread capture wiped by fees at all settings
- `nba-2025-26-rpg-leader-kel-el-ware` (sports): -$6.21 best PnL -- net loser
  at every spread tested
- `highest-temperature-in-chicago-on-ma...` (new_market): -$17.60 worst-case PnL
  -- volatile new_market with adverse price movement

| Market Slug | Bucket | Fills | Orders | Scenarios w/ Trades | Best PnL | Worst PnL |
|---|---|---|---|---|---|---|
| elon-musk-of-tweets-march-28-march-30-215-239 | near_resolution | 360 | 34 | 5 | -1.99 | -1.99 |
| will-a-different-combination-of-candidates-advance-to-t... | politics | 209 | 3 | 0 | 0.00 | 0.00 |
| will-jd-vance-talk-to-iranian-negotiators-by-april-30 | politics | 0 | 3 | 0 | 0.00 | 0.00 |
| will-daniel-mercuri-win-the-california-governor-electio... | politics | 1035 | 134 | 5 | -2.92 | -2.92 |
| will-jon-stewart-win-the-2028-democratic-presidential-n... | politics | 0 | 7 | 0 | 0.00 | 0.00 |
| will-jb-pritzker-win-the-2028-us-presidential-election | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| will-harvey-weinstein-be-sentenced-to-no-prison-time | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| will-jb-pritzker-win-the-2028-us-presidential-election | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| will-russia-capture-kostyantynivka-by-april-30 | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| will-trump-deport-less-than-250000 | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| will-russia-capture-lyman-by-june-30-2026-413 | politics | 0 | 0 | 0 | 0.00 | 0.00 |
| fif-col-fra-2026-03-29-draw | sports | 1271 | 1050 | 5 | 0.00 | 0.00 |
| will-duke-win-the-2026-ncaa-tournament | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| will-iowa-win-the-2026-ncaa-tournament | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| fif-lit-geo-2026-03-29-lit | sports | 1078 | 843 | 5 | 0.00 | 0.00 |
| will-the-tampa-bay-lightning-win-the-2026-nhl-stanley-cup | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| will-england-win-the-2026-fifa-world-cup-937 | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| j2100-mon-tsc-2026-03-29-mon | sports | 1289 | 1040 | 5 | 0.00 | 0.00 |
| will-duke-win-the-2026-ncaa-tournament | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| will-manchester-city-win-the-202526-english-premier-league | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| nba-2025-26-rpg-leader-kel-el-ware | sports | 1862 | 1517 | 5 | -6.21 | -6.21 |
| nba-2025-26-most-improved-player-deni-avdija | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| will-the-miami-heat-make-the-nba-playoffs-867 | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| nba-2025-26-apg-leader-trae-young | sports | 1757 | 1473 | 5 | -5.18 | -5.18 |
| will-max-verstappen-be-the-2026-f1-drivers-champion | sports | 0 | 0 | 0 | 0.00 | 0.00 |
| j2100-tok-koc-2026-03-29-tok | sports | 1317 | 1014 | 5 | 0.00 | 0.00 |
| highest-temperature-in-wellington-on-march-29-2026-20c | new_market | 2024 | 1625 | 5 | -7.04 | -7.04 |
| highest-temperature-in-miami-on-april-1-2026-82-83f | new_market | 1757 | 1406 | 5 | -2.42 | -2.42 |
| highest-temperature-in-hong-kong-on-march-29-2026-25c | new_market | 985 | 746 | 5 | 0.00 | 0.00 |
| highest-temperature-in-hong-kong-on-march-29-2026-25c | new_market | 985 | 746 | 5 | 0.00 | 0.00 |
| highest-temperature-in-chicago-on-march-29-2026-53forbelow | new_market | 1710 | 1367 | 5 | -17.60 | -17.60 |
| btc-updown-5m-1774771800 | crypto | 3140 | 6001 | 5 | -19.90 | -19.90 |
| sol-updown-5m-1774768800 | crypto | 4929 | 10000 | 5 | -492.34 | -492.34 |
| sol-updown-5m-1774771500 | crypto | 3639 | 7127 | 5 | -34.59 | -34.59 |

Note: Several politics and sports tapes show 0 fills AND 0 orders despite being Shadow
(Gold-tier) tapes.  These are low-activity markets where the strategy never found
conditions to submit an order during the shadow session.  They are classified as
executable-negative-or-flat (not structural-zero-fill) because they are Gold/Shadow
tapes and their zero-activity is a strategy/market-condition outcome, not a data-tier
failure.

---

### executable-positive (7 tapes)

**Why:** Crypto 5m markets (BTC/ETH/SOL) have high trade frequency and moderate
probabilities (typically 0.3-0.7 range), which is the optimal operating regime for
the logit Avellaneda-Stoikov market-maker.  High fill rates allow spread capture to
outrun fees.  The 3 negative crypto tapes experienced adverse price trends that
overwhelmed spread revenue; specifically `sol-updown-5m-1774768800` had a -$492.34
worst case, indicating a severe directional move during the shadow session.

| Market Slug | Bucket | Fills | Orders | Scenarios w/ Trades | Best PnL | Worst PnL |
|---|---|---|---|---|---|---|
| btc-updown-5m-1774769100 | crypto | 2521 | 12249 | 5 | 35.54 | -415.23 |
| btc-updown-5m-1774770900 | crypto | 1907 | 9017 | 5 | 8.79 | -145.00 |
| btc-updown-5m-1774770000 | crypto | 1912 | 9046 | 5 | 5.93 | -115.72 |
| btc-updown-5m-1774768200 | crypto | 2280 | 11034 | 5 | 4.67 | -364.56 |
| eth-updown-5m-1774769400 | crypto | 6621 | 27021 | 5 | 297.25 | -30.95 |
| eth-updown-5m-1774771200 | crypto | 5927 | 24264 | 5 | 99.81 | -30.47 |
| sol-updown-5m-1774769700 | crypto | 9724 | 38803 | 5 | 183.48 | -120.44 |

The best scenario IDs were: spread-x100 (BTC tapes), spread-x300 (ETH tapes),
spread-x100/x150 (SOL tapes).  The optimal spread is market-dependent; 7/10 crypto
tapes found at least one profitable scenario.

---

## Recommendation Matrix

| Option | Time-to-First-Dollar | Gate-2 Closure | Data Dependency | Strategy Risk | Overall |
|---|---|---|---|---|---|
| **Crypto-only corpus subset** | FAST | HIGH | LOW | LOW | Highest feasibility for Gate 2 closure. Blocked only by operator decision on scope change. |
| **Low-frequency strategy improvement** | SLOW | LOW | HIGH | HIGH | Lowest feasibility for Gate 2 closure in near-term. High strategy risk and data dependency with no clear timeline. |
| **Track 2 focus (standalone)** | MEDIUM | N/A | MEDIUM | MEDIUM | Fastest standalone revenue path. Does not close Gate 2; Track 1 deployment remains deferred. |

### Option 1: Crypto-only corpus subset

*Restrict Gate 2 evaluation to the crypto bucket only (requires operator approval to change gate scope).*

- **Time-to-First-Dollar:** `FAST` -- Crypto bucket already at 7/10 = 70% pass rate -- meets 70% threshold today with zero strategy or data changes.
- **Gate-2 Closure Feasibility:** `HIGH` -- 7/10 = 70% is >= 70% threshold.  Gate 2 closes immediately if scope is redefined to crypto-only.  Operator sign-off required.
- **Data Dependency:** `LOW` -- No new data required.  Existing crypto Gold/Shadow tapes already validated.  12 active 5m markets now available for continued capture.
- **Strategy Risk:** `LOW` -- Strategy (MarketMakerV1) is unchanged.  Only gate scope definition changes.

> **Verdict:** Highest feasibility for Gate 2 closure.  Blocked only by operator decision on scope change.

### Option 2: Low-frequency strategy improvement

*Improve strategy to generate positive PnL on politics / sports / near_resolution / new_market tapes.*

- **Time-to-First-Dollar:** `SLOW` -- 9 Silver tapes are structurally non-executable regardless of strategy.  Remaining executable-negative tapes require new calibration research, re-sweep, and validation cycles.
- **Gate-2 Closure Feasibility:** `LOW` -- Needs positive PnL on 35 additional tapes (politics=10, sports=15, near_resolution=10) to reach 70%.  No evidence current strategy can be tuned for low-frequency extreme-probability markets.
- **Data Dependency:** `HIGH` -- Silver tapes cannot produce fills regardless of strategy.  Requires Gold-tier re-capture of politics, sports, and near_resolution markets -- long timeline, uncertain availability.
- **Strategy Risk:** `HIGH` -- Would require significant changes to MarketMakerV1 calibration and spread-setting logic.  Risk of regression on crypto bucket which is currently profitable.

> **Verdict:** Lowest feasibility for Gate 2 closure in near-term.  High strategy risk and data dependency with no clear timeline.

### Option 3: Track 2 focus (standalone)

*Pursue crypto pair bot (Track 2 / Phase 1A) independently of Gate 2.*

- **Time-to-First-Dollar:** `MEDIUM` -- 12 active 5m crypto markets (BTC=4, ETH=4, SOL=4) available now.  Requires paper soak with real signals, oracle mismatch validation, and EU VPS setup before live deployment.
- **Gate-2 Closure Feasibility:** `N/A` -- Track 2 does not contribute to Gate 2 closure.  Track 1 market-maker deployment remains blocked.
- **Data Dependency:** `MEDIUM` -- Needs real-signal paper soak data.  Market availability confirmed 2026-04-14.  Minimal new infrastructure: pair-watch CLI exists.
- **Strategy Risk:** `MEDIUM` -- Crypto pair bot strategy validated in quick-049 pattern analysis.  Oracle mismatch (Coinbase vs Chainlink) is an open concern requiring paper-soak validation before live capital.

> **Verdict:** Fastest standalone revenue path.  Does not close Gate 2; Track 1 deployment remains deferred.

---

## Ranked Recommendation

| Rank | Option | Gate-2 Path | Revenue Path | Operator Action Required |
|---|---|---|---|---|
| 1 | Crypto-only corpus subset | YES -- closes Gate 2 immediately at 70% | YES -- unlocks Track 1 live deployment | Authorize scope change for Gate 2 |
| 2 | Track 2 focus (standalone) | NO -- Gate 2 remains FAILED | YES -- fastest standalone revenue; 12 active markets now | Authorize paper soak + VPS provisioning |
| 3 | Low-frequency strategy improvement | UNCERTAIN | NO -- very long timeline | Not recommended without new research evidence |

**Key evidence summary:**
- Option 1 (crypto-only subset) has the highest Gate-2 closure feasibility (7/10 = 70%,
  exactly the threshold) and requires no strategy changes or new data.
- Option 2 (Track 2) provides the fastest independent revenue path and is already
  unblocked as of 2026-04-14 when crypto markets returned (12 active 5m markets).
- Options 1 and 2 are not mutually exclusive -- both can proceed in parallel under
  the triple-track model.

This document presents evidence only.  The operator retains full authority over
which path to authorize.  No gate thresholds have been changed, no benchmark
manifests modified, and no strategy parameters altered.

---

## Artifacts Written

| File | Description |
|---|---|
| `artifacts/gates/gate2_sweep/failure_anatomy.json` | Machine-readable partition report with 50-tape classification and recommendation matrix |
| `artifacts/gates/gate2_sweep/failure_anatomy.md` | Human-readable markdown analysis with per-tape tables |
| `docs/dev_logs/2026-04-15_gate2_failure_anatomy.md` | This dev log |
| `tools/gates/gate2_failure_anatomy.py` | Partition classifier and report generator (rerunnable) |
| `tests/test_gate2_failure_anatomy.py` | Unit tests (25 passing) |

---

## Smoke Test

```
python -m pytest tests/test_gate2_failure_anatomy.py -v --tb=short
# 25 passed

python tools/gates/gate2_failure_anatomy.py
# [anatomy] Loaded 50 tapes
# structural-zero-fill: 9 tapes | fills=0 | buckets={'near_resolution': 9}
# executable-negative-or-flat: 34 tapes | fills=42247 | buckets={...}
# executable-positive: 7 tapes | fills=30892 | buckets={'crypto': 7}
# TOTAL: 50 tapes

python -c "import json; d=json.load(open('artifacts/gates/gate2_sweep/failure_anatomy.json')); \
  assert len(d['partitions']) == 3; \
  assert sum(p['count'] for p in d['partitions'].values()) == 50; \
  print('PASS: 50 tapes across 3 partitions')"
# PASS: 50 tapes across 3 partitions
```

---

## Codex Review

*Tier: Skip (docs, config, analysis scripts -- no execution layer code changed).*
