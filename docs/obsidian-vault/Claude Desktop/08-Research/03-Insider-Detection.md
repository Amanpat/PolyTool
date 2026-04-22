# Insider / Information Advantage Detection
**Status:** Researched, Phase 1 ready for implementation
**Last updated:** 2026-04-08
**Source:** GLM-5 Turbo research on informed trading detection

## Phase 1 — Simple Heuristic Detector (start here)

### Metric 1: Market-Adjusted Win Rate
For each wallet:
- Compute average implied probability at entry: p0 = mean(price at trade time)
- Compute observed win rate: p̂ = wins / total
- Binomial test: H0 = trades are independent with success prob p0
- Output: -log10(p-value) as "informedness score"
- Filters: N ≥ 30-50 trades, p̂ ≥ p0 + 0.15-0.20, total profit above threshold

**Python:** `scipy.stats.binom_test` or `binom.cdf` — trivial

### Metric 2: Pre-Event Trading Score
- Define events = large price moves (>5% in <30 min) as proxy events initially
- For each wallet: count trades in [t_event - τ, t_event) that are in correct direction
- τ windows to test: {5m, 30m, 1h, 6h, 1d}
- Null: trades uniformly distributed → N_pre ~ Binomial(N_total, τ/T)
- Multiple testing correction: Benjamini-Hochberg FDR

**Key insight from research:** A simple binomial test with N≥50 catches strong insiders with ~70-80% recall. False positive rate ~0.5-2% of all wallets.

### Minimum viable detector
Flag wallets where:
- N_trades ≥ 50
- Win rate ≥ baseline + 20%
- p-value ≤ 0.01
- Pre-event score ≥ threshold (calibrate empirically)

This alone catches the CBS-reported Polymarket insider cases and the Forbes $1M-in-24h wallet.

## Phase 2 — Statistical Rigor (after Phase 1 is running)
- Wallet-level VPIN: bucket volume, compute |V_buy - V_sell|, aggregate
- Kyle lambda: regress Δprice on net_order_flow per wallet per market
- Event study: abnormal returns around trades, t-statistics
- Calibration: shuffle wallet labels or timestamps to estimate false positive rates

## Phase 3 — Network Analysis (4-8 weeks after Phase 2)
- Funding graph: link on-chain funding addresses to prediction market deposits
- Community detection: Louvain/Leiden on funding graph
- Behavioral fingerprinting: time-of-day profile, market preferences, size distribution
- Pairwise similarity: cosine similarity between behavior profiles
- If one wallet in a cluster is flagged → upgrade others

## Phase 4 — Real-Time Integration (connects to Loop B + Loop D)
- Streaming pipeline maintains per-wallet aggregates incrementally
- Event feed (news API, Twitter, blockchain events) for real-time pre-event scoring
- Threshold-based alerts on newly flagged wallets or sudden score spikes

## Real-World Cases to Calibrate Against
- Polymarket: CBS (2026) insider trades before Iran/Venezuela events
- Polymarket: $7M UMA governance attack (coordinated voting + trading)
- Polymarket: Forbes $1M in 24 hours wallet
- Kalshi: CFTC sanctioned YouTube editor insider case
- General: UMA oracle manipulation + dispute period trading

## Ethical Framework
- System is for RISK MANAGEMENT, not law enforcement
- Tier 1 (strong informed): Do NOT copy, monitor closely
- Tier 2 (ambiguous): Monitor, consider delayed following
- Tier 3 (fast news / skilled analyst): Safe to copy with latency awareness

## Dependencies
- External event timestamp feed needed for pre-event scoring
- Initial proxy: use large price moves (>5% in <30 min) as "events"
- Future: RIS news/signals pipeline provides real event timestamps
