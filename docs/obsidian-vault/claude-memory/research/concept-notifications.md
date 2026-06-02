---
title: "Notifications"
type: concept
status: superseded
superseded_by: repo-docs/specs/spec-0015-discord-alerting-and-operator-notifications.md
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: stale
tags: [module, status/done, notifications]
---

# Notifications

Source: audit Section 1.1 — `packages/polymarket/notifications/` (2 files).

Discord webhook alerting for gate results, session events, and risk halts.

---

## Module Inventory

| Module | Purpose | Status |
|--------|---------|--------|
| `discord.py` | Discord webhook notification functions | WORKING |
| `__init__.py` | Package init | — |

---

## discord.py — 7 Functions

| Function | Description |
|----------|-------------|
| `post_message` | Low-level webhook POST |
| `notify_gate_result` | Gate pass/fail notification |
| `notify_session_start` | Strategy session started |
| `notify_session_stop` | Strategy session stopped |
| `notify_session_error` | Strategy session error |
| `notify_kill_switch` | Kill switch triggered |
| `notify_risk_halt` | Risk manager halt triggered |

**Behavioral contract:**
- All functions return `bool`, never raise
- `DISCORD_WEBHOOK_URL` environment variable required
- 5-second timeout on all webhook calls

---

## Gate Integration

Gate scripts (`tools/gates/`) fire `notify_gate_result()` inside `_write_gate_result()` via try/except:
- `close_replay_gate.py` — Gate 1
- `close_sweep_gate.py` — Gate 2
- `run_dry_run_gate.py` — Gate 4

---

## Live Runner Integration

`LiveRunConfig.notifier` is duck-typed. `LiveRunner.run_once()` fires:
- `notify_kill_switch` pre-tick (at most once per session)
- `notify_risk_halt` post-loop (at most once per session)

---

## Tests

29 tests in `tests/test_discord_notifications.py` — all offline (`requests.post` mocked).

---

## n8n Discord Alerting (separate from polytool discord.py)

The RIS n8n pilot sends Discord alerts via n8n webhook nodes using structured embed format. This is a separate alert path from the `discord.py` functions above. n8n alerts cover health checks, pipeline errors, ingest failures, and daily summaries. See `docs/runbooks/RIS_DISCORD_ALERTS.md`.

---

## Cross-References

- [[legacy/PolyTool/02-Modules/SimTrader]] — LiveRunner uses the notifier duck-type
- [[legacy/PolyTool/02-Modules/Gates]] — Gate scripts hook into notify_gate_result
- [[legacy/PolyTool/03-Strategies/Track-1B-Market-Maker]] — Discord alerting is a Phase 1B delivered item
- [[legacy/PolyTool/02-Modules/RIS]] — n8n pilot uses separate Discord alert path from polytool discord.py
- [[claude-memory/decisions/decision-ris-n8n-pilot-scope]] — Pilot scope boundary

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
