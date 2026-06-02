---
tags: [prompt-archive]
date: 2026-04-09
status: complete
model: GLM-5-Turbo
---
# CLOB WebSocket Model, Python Throughput, and Alchemy CU Costs

## Q1: CLOB WebSocket Subscription Model

**Critical finding: NO wildcard "all markets" mode.** Must subscribe per-asset_id.

- Endpoint: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- Subscription requires explicit `assets_ids` list — no "subscribe to everything"
- Each binary market has 2 token IDs (YES/NO), so hundreds of active markets = thousands of IDs
- **Dynamic subscription supported:** can add/remove asset_ids without reconnecting via `"operation": "subscribe"` / `"unsubscribe"`
- **New market detection:** set `custom_feature_enabled: true` → receive `new_market` events with `clob_token_ids`
- **PING required:** send text `"PING"` every 10 seconds or server closes connection
- **No documented subscription limit** per connection (test at scale)
- **SSE endpoint (`/events/trades`) is NOT documented** — do not rely on it
- **No replay on disconnect** — missed events are gone; backfill via REST `GET /trades`

### Subscription message format:
```json
{
  "assets_ids": ["<token_id_1>", "<token_id_2>"],
  "type": "market",
  "custom_feature_enabled": true
}
```

### Trade event format (`last_trade_price`):
```json
{
  "asset_id": "11412207...",
  "event_type": "last_trade_price",
  "fee_rate_bps": "0",
  "market": "0x6a67b9d8...",
  "price": "0.456",
  "side": "BUY",
  "size": "219.217767",
  "timestamp": "1750428146322"
}
```
Fields: asset_id, event_type, fee_rate_bps, market, price, side, size, timestamp. **No wallet address.**

### Market discovery for subscription management:
1. Initial: `GET https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100` (paginate)
2. Real-time: listen for `new_market` events on WebSocket
3. Cleanup: listen for `market_resolved` events → unsubscribe resolved asset_ids

## Q2: Python Throughput

- 150k-300k trades/day = 2-3/sec avg, 50/sec peaks
- **Single asyncio process handles this easily** — `websockets` benchmarks show 10k+ msg/sec
- Keep message handler non-blocking (no sync DB writes in hot path)
- Use `ping_interval=9.9` (Polymarket requires PING every 10s)
- Signs of falling behind: growing asyncio.Queue, increasing end-to-end latency
- **Scaling pattern if needed:** partition asset_ids across multiple connections, use asyncio.Queue → worker pool

### Recommended websockets config:
```python
connect(
    "wss://ws-subscriptions-clob.polymarket.com/ws/market",
    ping_interval=9.9,
    ping_timeout=15.0,
    max_size=2**20,  # 1 MiB
)
```

## Q3: Alchemy CU Costs

### eth_getLogs: **60 CU per call (flat)**
- Block range does NOT affect cost
- Number of results does NOT affect cost
- 100 blocks or 1000 blocks = same 60 CU

### eth_subscribe("logs") notifications: **~40 CU per notification**
- Priced by bandwidth: 0.04 CU per byte
- Typical OrderFilled event ~1000 bytes → ~40 CU
- Creating subscription: 10 CU (one-time)
- No maintenance fee

### Monthly estimate for our usage:
- 50 wallets × 20 trades/day × 30 days = 30,000 notifications
- 30,000 × 40 CU = **1,200,000 CU/month**
- 100 eth_getLogs/day × 30 days × 60 CU = **180,000 CU/month**
- **Total: ~1.38M CU/month** (well under 30M free tier)

### Free tier: 30M CU/month, 500 CU/s throughput
### PAYG: $0.45 per 1M CU (up to 300M), $0.40 above 300M
### Exceeding free tier: hard cutoff, must upgrade (no throttle mode)

### Official pricing URL: https://www.alchemy.com/docs/reference/compute-unit-costs

See [[08-Research/04-Loop-B-Live-Monitoring]], [[08-Research/01-Wallet-Discovery-Pipeline]]
