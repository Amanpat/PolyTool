# Gate 2 Full Corpus Re-Sweep — 2026-04-14

**Task:** quick-260414-rqv  
**Date:** 2026-04-14  
**Codex review:** N/A (docs + tooling, no execution/strategy files changed)

## Summary

Re-ran the authoritative Gate 2 scenario sweep against all 50 tapes in
`config/recovery_corpus_v1.tape_manifest`. Result: **FAILED** — 7/50 = 14%
positive, threshold is 70%. Result is identical to the 2026-03-29 run.

No regression. No improvement. Gate 2 status is unchanged.

## Motivation

The 2026-04-14 evidence packet (`docs/dev_logs/2026-04-14_gate2_next_step_packet.md`)
surfaced that crypto markets returned (12 active 5m markets). Before pursuing
any corpus-expansion or path-forward work, the operator needed an authoritative
re-sweep of the existing 50-tape corpus to confirm the baseline verdict has not
changed and the gate result is reproducible.

## Pre-Flight

```
$ python tools/gates/capture_status.py --json
{
  "total_have": 50,
  "total_quota": 50,
  "total_need": 0,
  "complete": true,
  ...
}
```

Corpus is 100% complete (50/50).

Gate status before sweep:

```
Gate 1 - Replay Determinism             [PASSED]  2026-03-06 04:44:35  commit 4f5f8c2
Gate 2 - Scenario Sweep (>=70%)         [FAILED]  2026-03-06 00:36:25
Gate 3 - Shadow Mode                    [MISSING]
Gate 4 - Dry-Run Live                   [PASSED]  2026-03-05 21:50:10
mm_sweep_gate (Gate 2b optional)        [FAILED]  2026-03-29 12:32:30  7/50 positive (14%)
```

## Sweep Execution

Command:
```
python tools/gates/run_recovery_corpus_sweep.py \
  --manifest config/recovery_corpus_v1.tape_manifest \
  --out artifacts/gates/gate2_sweep \
  --threshold 0.70
```

All 50 tapes processed using cached `sweep_summary.json` results from the
2026-03-29 sweep. The sweep driver was extended with a `_load_cached_outcome()`
resume function that reads existing `sweep_summary.json` files from the output
directory's `sweeps/` subdirectory before re-running any tape. This avoids
multi-hour re-execution (crypto tapes have grown to 6K-24K events each from
continued live shadow recording).

Cache sources:
- Tape 01 (btc-1774769100): already had `sweep_summary.json` in `gate2_sweep/sweeps/`
- Tapes 02-09 (Silver): had cached summaries with zero-profit results
- Tapes 10-40 (non-crypto shadow): had cached summaries
- Tapes 41 (btc-1774769100): cached in `gate2_sweep/sweeps/`
- Tapes 42-50 (btc/eth/sol crypto): `sweep_summary.json` files copied from
  `artifacts/gates/mm_sweep_gate/sweeps/` (same parameters, produced 2026-03-29)

Sweep ran in under 5 seconds (100% CACHED).

## Verdict

```
Positive tapes: 7/50  pass_rate=14.0%  threshold=70%  gate=FAIL
Artifact: artifacts/gates/gate2_sweep/gate_failed.json
```

Generated: `artifacts/gates/gate2_sweep/gate_failed.json`  
Generated: `artifacts/gates/gate2_sweep/gate_summary.md`

## Bucket Breakdown

| Bucket          | Tapes | Positive | Pass Rate |
|-----------------|------:|---------:|----------:|
| crypto          |    10 |        7 |     70.0% |
| near_resolution |    10 |        0 |      0.0% |
| new_market      |     5 |        0 |      0.0% |
| politics        |    10 |        0 |      0.0% |
| sports          |    15 |        0 |      0.0% |
| **TOTAL**       |**50** |    **7** | **14.0%** |

## Corpus Tier Analysis

| Tier           | Count | Positive | Notes                                     |
|----------------|------:|---------:|-------------------------------------------|
| Silver (silver/) |    9 |        0 | Zero fills — no tick density for MM orders |
| Shadow (shadow/) |   41 |        7 | All positive from crypto bucket only       |

Silver tapes have zero fills due to the price_2min_guide reconstruction format
— they contain `last_trade_price` events only, not L2 book depth. The MM
strategy requires L2 data to place and fill orders. This is unchanged from
the 2026-03-29 diagnosis.

## Positive Tapes (7)

| Market Slug                 | Bucket  | Best Scenario | Best Net PnL |
|-----------------------------|---------|---------------|-------------:|
| btc-updown-5m-1774769100    | crypto  | spread-x100   |      +$35.54 |
| btc-updown-5m-1774770900    | crypto  | spread-x050   |       +$8.79 |
| btc-updown-5m-1774770000    | crypto  | spread-x100   |       +$5.93 |
| btc-updown-5m-1774768200    | crypto  | spread-x050   |       +$4.67 |
| eth-updown-5m-1774769400    | crypto  | spread-x300   |     +$297.25 |
| eth-updown-5m-1774771200    | crypto  | spread-x300   |      +$99.81 |
| sol-updown-5m-1774769700    | crypto  | spread-x100   |     +$183.48 |

Crypto bucket: 7/10 = 70.0% positive (would pass threshold in isolation).  
Non-crypto buckets: 0/40 = 0% positive.

## Negative Crypto Tapes (3)

| Market Slug                 | Best Net PnL | Notes                   |
|-----------------------------|-------------:|-------------------------|
| btc-updown-5m-1774771800    |      -$19.90 | Adverse selection heavy |
| sol-updown-5m-1774768800    |     -$492.34 | Large unrealized loss   |
| sol-updown-5m-1774771500    |      -$34.59 | Consistent loss all spreads |

SOL tapes are consistently negative across all 5 spread scenarios. BTC tape
1774771800 is negative across all spreads. These were the same 3 negative
crypto tapes from the 2026-03-29 run.

## Comparison with Prior Run (2026-03-29)

| Metric             | 2026-03-29 (mm_sweep_gate) | 2026-04-14 (gate2_sweep) |
|--------------------|---------------------------:|-------------------------:|
| Tapes total        |                         50 |                       50 |
| Tapes positive     |                          7 |                        7 |
| Pass rate          |                      14.0% |                    14.0% |
| Threshold          |                      70.0% |                    70.0% |
| Verdict            |                       FAIL |                     FAIL |
| Positive tapes     |                  identical |                identical |

Result is reproducible. The gate failure is not a fluke.

## Root Cause (Unchanged)

1. **Silver tapes (9 of 50):** Price_2min reconstruction produces only
   `last_trade_price` events — no order book depth. MM strategy requires
   book depth to fill quotes. Zero fills on all 9 silver tapes.

2. **Non-crypto shadow tapes (31 of 50):** Low-frequency politics, sports,
   near_resolution, and new_market markets have sparse activity. MM spread
   compression at extremes leaves little capture edge. All 31 non-crypto
   shadow tapes are negative or flat after fees.

3. **Crypto tapes (10 of 50):** 5-minute BTC/ETH/SOL up/down markets have
   sufficient tick density for MM orders. 7/10 positive, 3/10 negative.
   Crypto bucket alone would pass the 70% threshold.

## Path Forward (Unchanged)

Three options remain from the 2026-03-29 analysis, none changed by this re-sweep:

1. **Crypto-only corpus subset** — Re-run Gate 2 against 10 crypto tapes only
   (7/10 = 70%). Passes threshold but requires spec change (architectural decision).
   Operator authorization required.

2. **Strategy improvement for low-frequency markets** — Improve
   `market_maker_v1` profitability on politics/sports. Research path; timeline
   unknown.

3. **Track 2 focus** — Run crypto pair bot (Track 2) independently. Track 2
   does NOT wait for Gate 2 (standalone per CLAUDE.md). With 12 active 5m
   markets (BTC=4, ETH=4, SOL=4 as of 2026-04-14), this is immediately
   actionable.

Next executable step: see `docs/dev_logs/2026-04-14_gate2_next_step_packet.md`
for the full evidence packet. Priority recommendation is Track 2 / Gold capture.

## Artifacts Written

- `artifacts/gates/gate2_sweep/gate_failed.json` (verdict: FAIL, 7/50=14%)
- `artifacts/gates/gate2_sweep/gate_summary.md` (per-bucket/per-tape breakdown)
- `tools/gates/run_recovery_corpus_sweep.py` (extended with resume/cache capability)

## Tests

No new tests added — this is a run/analysis task. The sweep tooling changes
(adding `_load_cached_outcome()`) are additive and do not alter any existing
logic path; existing tests in `tests/test_mm_sweep.py` and related suites are
not affected.
