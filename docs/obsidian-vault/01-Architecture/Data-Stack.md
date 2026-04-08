---
type: architecture
tags: [architecture, data, status/done]
created: 2026-04-08
---

# Data Stack

Source: roadmap "Multi-Layer Data Stack" section — Five Free Layers.

---

## The Key Insight

Hourly L2 anchor points from the pmxt archive transform reconstruction from "build from nothing" to "fill 60-minute gaps between known states." This makes Silver tape reconstruction viable without custom infrastructure.

---

## The Five Free Layers

### Layer 1 — pmxt Archive (hourly L2 snapshots)

`archive.pmxt.dev` — free hourly Parquet snapshots of full Polymarket AND Kalshi L2 orderbook and trade data.

- Structural anchor for Silver reconstruction
- Kalshi data included — enables cross-platform comparison in Phase 3
- Read directly by DuckDB without any import step
- Default path: `D:/polymarket_data/pmxt_archive/` (or equivalent on partner's machine)

### Layer 2 — Jon-Becker Dataset (72.1M trades, 7.68M markets, 36GB)

`github.com/Jon-Becker/prediction-market-analysis` — MIT license.

- Bronze tier tape source (trade-level only)
- Seeds `external_knowledge` RAG partition as PEER_REVIEWED
- Four key findings: maker +1.12%/trade; category gap table; favorite-longshot bias; post-Oct-2024 regime shift
- Read directly by DuckDB without any import step
- Default path: `D:/polymarket_data/jon_becker/`

### Layer 3 — polymarket-apis PyPI (2-minute price history)

Public, free, no API key required.

- 30 mid-price observations per 60-minute window
- Used in Silver reconstruction to constrain plausible midpoints
- Provides the `price_2min` ClickHouse table via `fetch-price-2min` CLI
- Code: `packages/polymarket/price_2min_fetcher.py` (322 lines)

### Layer 4 — Subgraph / Goldsky (on-chain confirmation + wallet attribution)

`warproxxx/poly_data` provides `orderFilled` events with maker/taker wallet addresses.

- 4-stage resolution cascade: ClickHouse → OnChainCTF → Subgraph → Gamma
- Code: `packages/polymarket/subgraph.py` (~150 lines)
- Also: `packages/polymarket/on_chain_ctf.py` (~180 lines) — raw JSON-RPC, no web3.py

### Layer 5 — Live Tape Recorder (non-negotiable, accumulates from now)

Tick-level millisecond data. Only source of true microstructure.

- Code: `packages/polymarket/simtrader/tape/recorder.py` (300 lines)
- Output: Gold tier tapes under `artifacts/tapes/gold/`
- Required for Gate 3 shadow validation and A-S calibration

---

## Silver Reconstruction Algorithm

```
FOR each market, FOR each 60-minute window between pmxt hourly snapshots:
  1. ANCHOR: Load L2 book state at window start (pmxt Parquet)
  2. FILL EVENTS: Load all trades in window (Jon-Becker dataset)
  3. MID-PRICE TRACK: Load 2-min price history (polymarket-apis)
  4. INTERPOLATE: Between fills, assume book persists unless mid-price moves
  5. OUTPUT: Tagged source='reconstructed', reconstruction_confidence='medium'
```

---

## What Goes Where

| Data Type | Database | Why |
|-----------|----------|-----|
| Live fills, tick data, WS events | ClickHouse | High-throughput concurrent writes, compression |
| pmxt Parquet, Jon-Becker (historical) | DuckDB | Zero-import native Parquet reads |
| Autoresearch experiment ledger | DuckDB | Research queries, no streaming writes |
| SimTrader sweep results | DuckDB | Join-heavy analytics |
| Tape metadata (path, tier, market, date) | ClickHouse | Live tape recording metadata |
| Resolution signatures | ClickHouse | Updated continuously |
| Signal reactions (t+5/30/120) | ClickHouse | Time-series, streaming inserts |

---

## Cross-References

- [[Database-Rules]] — ClickHouse/DuckDB one-sentence rule, all 23 tables
- [[System-Overview]] — Layer roles and package structure
- [[Tape-Tiers]] — Gold/Silver/Bronze tape definitions using these layers
