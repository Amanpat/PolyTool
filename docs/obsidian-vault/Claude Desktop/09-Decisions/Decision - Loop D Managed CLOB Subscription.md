---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — Loop D Uses Managed CLOB Subscription (Not Wildcard)

## Context
Research confirmed the Polymarket CLOB WebSocket has NO wildcard "all markets" mode. Must subscribe per-asset_id. This means Loop D can't simply "listen to everything" — it must actively manage a subscription set of all active token IDs.

## Decision
Loop D maintains a **managed subscription** to all active markets:

1. **Bootstrap:** On startup, fetch all active markets via Gamma API (`events?active=true&closed=false`), extract all token IDs, subscribe to all of them
2. **Maintain:** Listen for `new_market` events (enabled by `custom_feature_enabled: true`) → auto-subscribe to new token IDs
3. **Cleanup:** Listen for `market_resolved` events → unsubscribe resolved token IDs
4. **Reconnect:** On disconnect, re-bootstrap from Gamma API (no replay of missed events)

This is more engineering than a wildcard subscription but is manageable — Polymarket has hundreds to low-thousands of active markets, and dynamic subscription lets us add/remove without reconnecting.

## Cost Impact
- CLOB WebSocket: still **free** (no CU cost regardless of subscription count)
- Alchemy (Loop B only): ~1.38M CU/month for 50 wallets + 100 eth_getLogs/day — **well under 30M free tier**
- Total infrastructure cost for all four loops: **$0/month** on free tiers

## Trade Data Limitation Confirmed
CLOB `last_trade_price` events contain: asset_id, price, size, side, timestamp, fee_rate_bps, market. **No wallet address.** Wallet attribution still requires Alchemy `eth_getLogs` (60 CU per query, on-demand only).

## Alternatives Considered
- SSE endpoint `/events/trades`: NOT documented, cannot rely on it
- Subscribe only to high-volume markets: would miss anomalies on obscure markets (which is where insider trading happens)
- Multiple WebSocket connections: not needed yet — no documented subscription limit per connection

See [[11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU]], [[08-Research/04-Loop-B-Live-Monitoring]]
