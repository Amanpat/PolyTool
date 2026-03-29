# Dev Log: gabagool22 Crypto Trading Pattern Analysis

**Date:** 2026-03-29
**Quick Task:** 48
**Branch:** phase-1B

## Objective

Run the scan + wallet-scan + alpha-distill pipeline against gabagool22 and produce a
structured gap report identifying which crypto-pair-specific dimensions the pipeline can
vs. cannot answer.

## What Was Run

1. `python -m polytool scan --user @gabagool22 --lite --ingest-positions --compute-pnl`
   - Resolved: wallet `0x640a5ad3a76ec6e56100298fab949fc7df8cf359`
   - 4,000 trades ingested, 50 positions in 30d window, CLV enriched
   - Scan completed in 46s

2. `python -m polytool wallet-scan --input /tmp/gabagool22_input.txt --profile lite`
   - Successful, same scan results stored under wallet_scan/ hierarchy

3. `python -m polytool alpha-distill --wallet-scan-run <run-dir>`
   - 0 candidates (expected: min_users_persistence=2 requires multi-wallet input)

## Key Findings

### gabagool22 is EXCLUSIVELY a crypto pair trader

- 100% of 50 positions are BTC/ETH 5m updown bracket markets
- 66% BTC, 34% ETH, 0% SOL in 30d window
- All 5m duration — no 15m brackets
- 92% complete-pair rate: 24/26 brackets have both UP and DOWN legs

### Pair cost data (computable via dossier.json post-processing)

- Average pair cost: $1.0274 (slightly above $1.00)
- 10/24 pairs (42%) were acquired below $1.00 — potentially profitable
- Range: $0.803 to $1.184

### CLV breakdown

- Overall: -0.035 notional-weighted (slightly negative)
- Favorite tier (25 positions, high-price leg): +0.087 — POSITIVE EDGE
- Deep underdog (10 positions): -0.263 — strong negative edge
- The positive edge is concentrated in the high-price side of pairs (>$0.65 entry)

### Category pipeline gap confirmed

- category_coverage = 0% because ClickHouse market_tokens table has no entries for
  these crypto bracket token IDs (the local DB is not populated with bracket market metadata)
- This is a known gap in the local data plane, not specific to gabagool22

### Detector signals

All four detectors fired at maximum or near-maximum:
- COMPLETE_SET_ARBISH: 1.0 (ARB_LIKELY) — confirms pair buying
- DCA_LADDERING: 1.0 (DCA_LIKELY) — multiple entries per bracket
- MARKET_SELECTION_BIAS: 1.0 (CONCENTRATED) — exclusively crypto
- HOLDING_STYLE: 0.937 (SCALPER) — avg 3.52 minutes to close

## Gap Report Location

`artifacts/debug/gabagool22_crypto_gap_report.md`

Six gap dimensions documented:
1. Pair cost — computable but not a pipeline output (needs new segment dimension)
2. Maker/taker split — not in dossier.json (needs trade-level field)
3. Bracket entry timing — not computed (needs slug-suffix parsing)
4. Second leg fill timing — not at position level (needs trade-level analysis)
5. Position sizing histogram — partial (averages available, distribution not)
6. Symbol/duration breakdown — not in pipeline (needs slug pattern segment axis)

## Signal Value Assessment

gabagool22 is a HIGH-VALUE reference wallet for Track 2 crypto pair bot:
- Confirms pair accumulation pattern is practiced in real markets
- Provides benchmark pair cost data ($1.0274 avg, 42% under $1.00)
- Confirms BTC/ETH 5m as the primary bracket type
- Positive CLV in the favorite tier (+0.087) on the high-price leg is a usable signal

All 4 non-answered gap dimensions can be addressed without new external data sources:
slug pattern parsing and trade-level timestamp alignment are sufficient.

## No Pipeline Code Modified

Per plan constraint: zero changes to scan pipeline code.
