---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — Watchlist Storage in ClickHouse

## Context
Loops A and D need to promote wallets to the Loop B watchlist. Need a storage mechanism that Loop B can read dynamically.

## Decision
Store the watchlist in a ClickHouse table. Follows the "live streaming writes → ClickHouse" rule.

Schema (proposed):
- wallet_address (String, primary)
- added_by (String: 'loop_a' | 'loop_d' | 'manual')
- added_at (DateTime)
- reason (String)
- priority (UInt8: 1-5)
- active (UInt8: 1/0)
- last_activity (DateTime, nullable)
- metadata (String, JSON blob for source-specific context)

Loop B reads this table on startup and polls for changes every 60 seconds. When a new address appears, it dynamically adds it to the Alchemy WebSocket subscription filter.

See [[08-Research/01-Wallet-Discovery-Pipeline]]
