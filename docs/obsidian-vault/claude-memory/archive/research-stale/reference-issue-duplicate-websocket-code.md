---
title: "Issue: Duplicate WebSocket Connection Code"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
tags: [issue, websocket, status/open]
---

# Issue: Duplicate WebSocket Connection Code

Source: audit Section 7.5.

WebSocket reconnection and event streaming logic is implemented independently in four separate files.

---

## Affected Files

| File | Lines | Purpose |
|------|-------|---------|
| `packages/polymarket/crypto_pairs/clob_stream.py` | 379 | CLOB stream for crypto pair bot |
| `packages/polymarket/simtrader/shadow/runner.py` | — | Shadow mode WS stream |
| `packages/polymarket/simtrader/tape/recorder.py` | 300 | Gold tape recorder |
| `packages/polymarket/simtrader/activeness_probe.py` | ~250 | Activeness probe |

Each implements its own:
- Reconnect-on-error loop
- Stall detection
- Event normalization

No shared WebSocket base class exists.

---

## Risk

- Bugs fixed in one implementation may not be fixed in others
- Reconnect backoff strategies may diverge over time
- Stall detection timeouts are hardcoded independently (e.g., 30s default in shadow runner)

---

## Resolution

Extract a shared `WebSocketBase` class or `ws_connect()` helper with standard reconnect logic, stall detection, and event normalization. Each consumer then subclasses or configures the shared base.

---

## Cross-References

- [[legacy/PolyTool/02-Modules/SimTrader]] — shadow runner and tape recorder
- [[legacy/PolyTool/02-Modules/Crypto-Pairs]] — clob_stream.py

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
