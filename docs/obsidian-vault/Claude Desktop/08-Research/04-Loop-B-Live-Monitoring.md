# Loop B — Live Wallet Monitoring Architecture
**Status:** Researched, architecture decided
**Last updated:** 2026-04-08
**Source:** GLM-5 Turbo research on Polymarket on-chain event monitoring

## Recommended Architecture

**Primary:** Alchemy Polygon WebSocket `eth_subscribe("logs")`
- Subscribe to OrderFilled events from both CTF Exchange contracts
- Filter topic1/topic2 for watched wallet addresses (20-50)
- Latency: <1-3 seconds from block production
- Free tier: 30M compute units/month (sufficient)
- Persistent WebSocket connection supported

**Backup:** Alchemy Custom Webhook (HTTP POST on matching events)
**Robust alternative:** Goldsky Turbo pipeline (managed, at-least-once delivery)

## Contract Details

| Contract | Address |
|----------|---------|
| CTFExchange | 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E |
| NegRiskCTFExchange | 0xC5d563A36AE78145C45a50134d48A1215220f80a |

**Event:** `OrderFilled(orderHash, maker, taker, makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee)`
- `maker` = topic1 (indexed, filterable)
- `taker` = topic2 (indexed, filterable)

## Key Finding: Off-Chain CLOB Limitation

**Cannot monitor other wallets' orders before on-chain fill.**
- Polymarket User Channel WebSocket requires YOUR L2 API credentials
- It streams MATCHED → MINED → CONFIRMED for YOUR orders only
- For OTHER wallets, earliest signal is always on-chain OrderFilled
- REST `GET /trades?user=<address>` exists but is polling, not real-time

**Implication:** Copy-trading has minimum ~1-3 second delay from target wallet's fill to our detection. For most prediction markets (not HFT), this is acceptable.

## Python Implementation Stack
- `websockets` library for WebSocket connection
- `eth-abi` or `web3.py` for decoding OrderFilled event data
- Standard asyncio event loop for processing

## Provider Comparison

| Provider | Free Tier | Latency | WebSocket | Best For |
|----------|-----------|---------|-----------|----------|
| Alchemy | 30M CU/mo, 5 webhooks | <1-3s | Yes | Primary (best docs, reliability) |
| Infura | 3M credits/day | <1-3s | Yes | Backup |
| QuickNode | 10M credits trial | <1-3s | Yes | Alternative |
| Goldsky | 1 pipeline + 1M writes/mo | Few seconds | No (webhook) | Robust managed pipeline |
| The Graph | 100k queries/mo | Minutes | No | Historical only, NOT real-time |

## Open Questions
- [ ] Estimate Alchemy CU consumption for 50-wallet continuous subscription
- [ ] Test WebSocket reconnection behavior (Polygon node restarts, Alchemy maintenance)
- [ ] Design watchlist management: how to add/remove addresses without restarting subscription


## UPDATED 2026-04-09: Two-Feed Architecture

Research revealed Polymarket CLOB WebSocket is free and faster than Alchemy for all-events monitoring. Architecture now uses TWO feeds:

### Feed 1: Polymarket CLOB WebSocket (Loop D — all trades)
- `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **Free**, no CU cost, parsed JSON, millisecond latency
- Subscribes to ALL trades platform-wide
- **Limitation:** No wallet addresses in the feed (only asset_id, price, size, side)
- **Use for:** Price anomaly detection, volume spike detection, market-level patterns

### Feed 2: Alchemy WebSocket (Loop B — wallet-specific)
- `eth_subscribe("logs")` filtered by 20-50 wallet addresses
- Low CU cost (~few thousand events/day for 50 wallets)
- **Has wallet addresses** (maker/taker in OrderFilled event)
- **Use for:** Wallet-specific trade attribution, copy-trade signals

### How They Work Together for Loop D
1. CLOB feed detects anomaly: "Massive volume spike on obscure market X in last 5 minutes"
2. System queries on-chain data (Alchemy REST, not WebSocket) for recent OrderFilled events on market X
3. Extracts wallet addresses of traders involved
4. Cross-references with known wallets and runs anomaly detectors
5. If flagged → promote to Loop B watchlist + trigger Loop C

This solves the cost problem: Loop D monitors everything for free via CLOB, then uses targeted Alchemy queries only when anomalies are detected.


## UPDATED 2026-04-09: All Technical Questions Resolved

### Alchemy CU Budget Confirmed
- Loop B (50 wallets): ~1.2M CU/month from notifications
- Loop D on-demand queries: ~180K CU/month (100 eth_getLogs/day)
- **Total: ~1.38M CU/month — uses only 4.6% of free tier (30M CU)**
- Massive headroom for scaling to more wallets or more queries

### eth_getLogs is Cheap
- 60 CU per call, FLAT (block range and result count don't matter)
- Can query 30 minutes of blocks in one call for 60 CU
- This makes Loop D's two-step approach very efficient: detect anomaly via CLOB (free) → identify wallets via eth_getLogs (60 CU)

### Notification Cost Clarified
- NOT a flat 16 CU as previously assumed
- Priced by bandwidth: 0.04 CU per byte, typical OrderFilled ~1000 bytes = ~40 CU
- Still very cheap for our usage pattern
