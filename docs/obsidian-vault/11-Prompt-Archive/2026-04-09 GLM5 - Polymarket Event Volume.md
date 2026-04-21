---
tags: [prompt-archive]
date: 2026-04-09
status: complete
model: GLM-5-Turbo
---
# Polymarket OrderFilled Event Volume Estimation

## Key Findings

### Daily Event Volume
- Average day: **150,000 - 300,000** OrderFilled events
- Moderate news day: 500k - 800k events
- Peak day (US Election Night): **3,000,000 - 4,500,000** events
- Peak is 10-15x average
- ~80%+ events on NegRiskCTFExchange (0xC5d5...)

### Alchemy CU Cost for ALL Events
- Average day: 250k × 16 CU = **4M CU/day**
- Average month: **120M CU/month**
- Peak day: **56M CU/day**
- **Free tier (30M CU/mo): ABSOLUTELY NOT FEASIBLE**
- Would exhaust monthly budget in 7.5 days average, 13 hours on peak day

### CRITICAL FINDING: Don't Use Alchemy for All-Events

**Polymarket provides a FREE public trade stream that is BETTER than on-chain:**

- **WebSocket:** `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **SSE:** `https://clob.polymarket.com/events/trades`

**Why this is superior to Alchemy:**
1. **0 CUs** — bypasses Alchemy entirely
2. **Parsed JSON** — no ABI decoding needed
3. **Lower latency** — milliseconds (CLOB match time) vs 1-2s (block confirmation)
4. **Filterable** — subscribe to specific asset_ids or markets

**Response format:**
```json
{
  "asset_id": "21742633...",
  "price": "0.65",
  "size": "150.00",
  "side": "BUY",
  "timestamp": "1704067200000"
}
```

## ARCHITECTURAL IMPACT

This changes Loop B AND Loop D design:

**Loop B (watchlist):** Keep Alchemy WebSocket for wallet-specific monitoring (20-50 addresses, low CU cost). This is the RIGHT use for Alchemy — targeted, filtered, cheap.

**Loop D (platform-wide anomaly detection):** Use Polymarket CLOB WebSocket/SSE feed instead of Alchemy. Subscribe to ALL trades for free. Process locally to detect anomalies.

**Key limitation:** CLOB feed doesn't include wallet addresses (only asset_id, price, size, side). For wallet attribution, we still need on-chain data. So:
- CLOB feed = real-time price/volume anomaly detection (free, fast)
- Alchemy filtered subscription = wallet-specific trade attribution (cheap, targeted)
- These are complementary, not competing

See [[08-Research/04-Loop-B-Live-Monitoring]] and [[08-Research/01-Wallet-Discovery-Pipeline]]
