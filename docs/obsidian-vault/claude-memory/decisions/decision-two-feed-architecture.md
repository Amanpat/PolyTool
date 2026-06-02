---
title: "Decision — Two-Feed Architecture for Live Monitoring"
type: decision
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
decided_at: 2026-04-09
decided_by: operator
tags: [decision]
---
# Decision — Two-Feed Architecture for Live Monitoring

## Context
Research estimated 150k-300k OrderFilled events/day on Polymarket (3-4.5M on peak days). Subscribing to ALL events via Alchemy WebSocket would consume 120M CU/month — 4x the free tier limit.

## Decision
Use two complementary data feeds:

1. **Polymarket CLOB WebSocket** (free, faster) for platform-wide trade monitoring (Loop D)
   - No wallet addresses, but detects anomalous market activity
2. **Alchemy WebSocket** (filtered, cheap) for wallet-specific monitoring (Loop B)
   - Has wallet addresses via OrderFilled event indexed fields
   - Only 20-50 wallets = minimal CU consumption

When CLOB feed detects an anomaly, targeted Alchemy REST queries identify the wallets involved.

## Alternatives Considered
- Alchemy all-events: 120M CU/month, not feasible on free tier
- Goldsky pipeline: viable but more setup, webhook-based not WebSocket
- Subgraph polling: too slow for real-time

## Impact
- Loop D becomes free to operate (CLOB feed costs nothing)
- Loop B stays cheap (targeted Alchemy subscription)
- Two-step anomaly detection: WHAT happened (CLOB) → WHO did it (Alchemy)

See [[legacy/Claude Desktop/08-Research/04-Loop-B-Live-Monitoring]], [[claude-memory/prompts/2026-04-09-glm5-polymarket-event-volume]]

## Connections

- [[claude-memory/decisions/_index]]
- [[index|Vault Home]]
