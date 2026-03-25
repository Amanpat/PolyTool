# Feature: Discord Alerting — Track A

**Status:** SHIPPED (partial — see deferred items)
**Spec:** [SPEC-0015](../specs/SPEC-0015-discord-alerting-and-operator-notifications.md)
**Branch:** simtrader

---

## Summary

Thin, testable Discord webhook notification layer for PolyTool Track A
operator alerts.  Covers gate pass/fail events and live runner kill-switch
and risk-halt events.

---

## What was built

### New module: `packages/polymarket/notifications/discord.py`

Stateless transport layer.  All functions return `bool` and never raise.

| Function | Purpose |
|----------|---------|
| `post_message(text)` | Core transport — posts markdown to webhook |
| `notify_gate_result(gate, passed, ...)` | Gate pass/fail alert |
| `notify_session_start(mode, strategy, asset_id)` | Session opened |
| `notify_session_stop(mode, strategy, asset_id)` | Session closed |
| `notify_session_error(context, exc)` | Runtime error |
| `notify_kill_switch(path)` | Kill switch tripped |
| `notify_risk_halt(reason)` | Risk manager halt |

### Gate script hooks (3 scripts)

`_write_gate_result()` in each gate script now fires `notify_gate_result()`
after writing the artifact:

- `tools/gates/close_replay_gate.py` — Gate 1
- `tools/gates/close_sweep_gate.py` — Gate 2
- `tools/gates/run_dry_run_gate.py` — Gate 4

Hook is inside a `try/except Exception: pass` block — never affects gate
script exit code.

### LiveRunner notifier hooks

`LiveRunConfig.notifier` — duck-typed optional notifier (default `None`).

When set, `LiveRunner.run_once()` fires:
- `notify_kill_switch()` — on the first kill-switch trip per session
- `notify_risk_halt()` — on the first risk-halt per session

Both fire at most once per `LiveRunner` instance.  Notifier exceptions are
swallowed; the kill-switch `RuntimeError` is always re-raised.

Wire Discord to a `LiveRunner`:
```python
import packages.polymarket.notifications.discord as _discord

config = LiveRunConfig(..., notifier=_discord)
runner = LiveRunner(config)
```

### Tests

`tests/test_discord_notifications.py` — 29 tests, all offline (no real HTTP).

### Configuration

`.env.example` — new entry:
```
DISCORD_WEBHOOK_URL=
```

---

## Deferred

The following integration points require CLI-level session orchestration, which
is a separate task:

| Event | Deferred reason |
|-------|----------------|
| Session start/stop | `LiveRunner` is tick-level; session loop is in CLI |
| Session error / WS reconnect | Requires hook in `ShadowRunner` and CLI exception handler |
| Gate 3 (shadow) | Manual gate; no CLI hook |

The `notify_session_start`, `notify_session_stop`, and `notify_session_error`
functions are implemented and tested.  Only the call sites in the CLI are
missing.

---

## Operator activation checklist (Stage 0 prerequisite)

1. Copy `.env.example` to `.env`, set `DISCORD_WEBHOOK_URL=<your webhook URL>`.
2. Run `python tools/gates/run_dry_run_gate.py` — a Gate 4 pass/fail notification should arrive in Discord.
3. Confirm the message appeared before starting Stage 0.

See [SPEC-0015 §6](../specs/SPEC-0015-discord-alerting-and-operator-notifications.md) for full operator expectations.
