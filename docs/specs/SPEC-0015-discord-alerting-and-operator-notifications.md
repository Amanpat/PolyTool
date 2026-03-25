# SPEC-0015: Discord Alerting and Operator Notifications

**Status:** Accepted
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## 1. Purpose and scope

Define the Discord alerting layer for PolyTool Track A: what events are
surfaced, how they are delivered, what failures are tolerated, and what
remains the operator's responsibility.

Discord is the canonical Track A alerting channel as stated in SPEC-0012 §6.
This spec defines the implementation contract so the layer can be built,
tested, and reasoned about independently of strategy logic.

**In scope:**
- Transport module (`packages/polymarket/notifications/discord.py`)
- Event taxonomy for gate and runtime events
- Environment and configuration contract
- Failure tolerance requirements
- Integration points in gate scripts and `LiveRunner`
- Test strategy

**Out of scope:**
- FastAPI endpoints that forward alerts (automation layer, deferred)
- n8n workflow triggers (deferred until Stage 0 complete)
- Grafana webhook annotations (deferred)
- Telegram or any alternative transport
- Alert routing, escalation, or on-call policies
- Message persistence or replay

---

## 2. Event taxonomy

All events that the notification layer emits.  For each event, the table lists
the source code location where the hook is wired, the function called, and the
deferral status.

### 2.1 Gate events

| Event | Source | Function | Status |
|-------|--------|----------|--------|
| Gate pass | `tools/gates/close_replay_gate.py` `_write_gate_result()` | `notify_gate_result(gate, passed=True, ...)` | **WIRED** |
| Gate fail | same | `notify_gate_result(gate, passed=False, detail=failure_reason)` | **WIRED** |
| Gate pass | `tools/gates/close_sweep_gate.py` `_write_gate_result()` | `notify_gate_result(...)` | **WIRED** |
| Gate fail | same | `notify_gate_result(...)` | **WIRED** |
| Gate pass | `tools/gates/run_dry_run_gate.py` `_write_gate_result()` | `notify_gate_result(...)` | **WIRED** |
| Gate fail | same | `notify_gate_result(...)` | **WIRED** |
| Gate 3 (shadow) pass/fail | `artifacts/gates/shadow_gate/gate_passed.json` written by operator | — | DEFERRED — manual gate; no CLI hook |

### 2.2 Runtime events

| Event | Source | Function | Status |
|-------|--------|----------|--------|
| Kill-switch tripped | `LiveRunner.run_once()` (pre-tick check) | `notifier.notify_kill_switch(path, context=...)` | **WIRED** |
| Risk manager halt | `LiveRunner.run_once()` (post-order loop) | `notifier.notify_risk_halt(reason)` | **WIRED** |
| Session start | CLI session loop | `notify_session_start(mode, strategy, asset_id)` | DEFERRED — CLI not wired |
| Session stop (clean) | CLI session loop | `notify_session_stop(mode, strategy, asset_id, summary)` | DEFERRED — CLI not wired |
| Session error | CLI session loop | `notify_session_error(context, exc)` | DEFERRED — CLI not wired |
| WS reconnect failure | `ShadowRunner` / live WS loop | `notify_session_error(...)` | DEFERRED — shadow runner not wired |

### 2.3 Deferred rationale

Session lifecycle (start/stop/error) requires a session-scoped orchestration
layer.  `LiveRunner` is a single-tick abstraction; the session loop lives in
`tools/cli/simtrader.py`.  Wiring session events to that CLI layer is a
separate integration task deferred from this spec.  The notification module
already has `notify_session_start`, `notify_session_stop`, and
`notify_session_error` implemented and tested — only the call sites are missing.

---

## 3. Transport contract

### Module: `packages/polymarket/notifications/discord.py`

All public functions share the same failure contract:

```
return type: bool
True  → HTTP 2xx from webhook
False → any other outcome (no URL, HTTP error, network error, exception)
raises: never
```

Functions must never raise to callers.  Notifications are best-effort
auxiliary signals; they must not affect the primary execution path.

### Public API

| Function | Arguments | Purpose |
|----------|-----------|---------|
| `post_message(text, *, webhook_url)` | `text: str` | Core transport; posts markdown string |
| `notify_gate_result(gate, passed, *, commit, detail, webhook_url)` | see below | Gate pass/fail notification |
| `notify_session_start(mode, strategy, asset_id, *, dry_run, webhook_url)` | — | Session opened |
| `notify_session_stop(mode, strategy, asset_id, *, summary, webhook_url)` | — | Session closed cleanly |
| `notify_session_error(context, exc, *, webhook_url)` | — | Runtime exception |
| `notify_kill_switch(path, *, context, webhook_url)` | — | Kill switch tripped |
| `notify_risk_halt(reason, *, context, webhook_url)` | — | Risk manager halt |

The `webhook_url` keyword argument on every function overrides the
environment variable.  It is used exclusively by tests — production code
should not pass it.

### Discord payload schema

All messages use the standard Discord webhook payload:

```json
{"content": "<markdown string>"}
```

No embeds, no files, no mentions.  Keep messages short and scannable.

---

## 4. Environment and configuration contract

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Optional | Full Discord incoming webhook URL.  If absent or empty, all notifications silently no-op (return False). |

The variable is read at call time via `os.environ.get()`, not at import time.
This means the value can be changed between calls in tests.

No other configuration is required.  Timeout is hardcoded to 5 seconds and is
not operator-configurable.

### LiveRunner notifier wiring

`LiveRunConfig.notifier` accepts any duck-typed object exposing:

```python
notifier.notify_kill_switch(path: str, *, context: Optional[str]) -> bool
notifier.notify_risk_halt(reason: str, *, context: Optional[str]) -> bool
```

Pass `packages.polymarket.notifications.discord` as the notifier module:

```python
import packages.polymarket.notifications.discord as _discord

config = LiveRunConfig(
    ...,
    notifier=_discord,
)
runner = LiveRunner(config)
```

When `notifier=None` (the default), all notification logic is bypassed
without any overhead.

---

## 5. Failure behavior

| Scenario | Behavior |
|----------|----------|
| `DISCORD_WEBHOOK_URL` not set | `post_message` returns False immediately; no network call |
| Webhook returns non-2xx | `post_message` returns False; execution continues normally |
| Network timeout (> 5s) | `requests.post` raises; caught internally; returns False |
| Notifier object raises | Caught with `except Exception: pass` at call site in `LiveRunner.run_once()` |
| Discord module import fails | Caught with `except Exception: pass` at call site in gate scripts |
| Repeated kill-switch trips | Notification fires only once per `LiveRunner` session (flag `_kill_switch_notified`) |
| Repeated risk halts | Notification fires only once per `LiveRunner` session (flag `_risk_halt_notified`) |

**Core invariant**: no notification call may cause the gate script to return a
wrong exit code, nor cause `LiveRunner.run_once()` to return without re-raising
a `RuntimeError` from the kill switch.  The kill switch `RuntimeError` is
always re-raised after the notification attempt, regardless of notification
success.

---

## 6. Operator expectations

### Stage 0 prerequisite

SPEC-0012 §8 states: "Discord alerts wired and confirmed active" is a Stage 0
prerequisite.  To satisfy this:

1. Set `DISCORD_WEBHOOK_URL` in `.env` (copied from `.env.example` template).
2. Run `python tools/gates/run_dry_run_gate.py` — a Gate 4 pass notification
   should appear in the configured Discord channel.
3. Manually verify the message arrived before starting Stage 0.

### Operator must acknowledge

The notification layer fires alerts but does not wait for acknowledgment.
The operator is responsible for:

- Monitoring the Discord channel for the duration of any live session.
- Acknowledging and investigating any kill-switch or risk-halt alert.
- Not restarting a session after an alert without a documented root cause.

Per SPEC-0012 §9, if "Discord alerts fire with no operator acknowledgment
available," that is an operator stop condition.

### Alert volume

Under normal Stage 0 operation, expected alert volume is:
- Gate events: one per gate closure run (infrequent)
- Kill-switch and risk-halt: zero in a clean session; one each if triggered

The layer does not send periodic heartbeats.  Absence of alerts is not a
confirmation the session is healthy; Grafana panels provide continuous
monitoring.

---

## 7. Test strategy

### Test file

`tests/test_discord_notifications.py` — 29 tests, all offline.

### Coverage

| Area | Tests |
|------|-------|
| `post_message` — no URL / empty URL | 2 |
| `post_message` — HTTP ok | 1 |
| `post_message` — correct JSON body | 1 |
| `post_message` — HTTP error | 1 |
| `post_message` — network exception | 1 |
| `post_message` — URL kwarg override | 1 |
| `notify_gate_result` — pass/fail labels, detail, underscores | 5 |
| `notify_session_start` — dry-run / live labels | 2 |
| `notify_session_stop` — basic fields, summary stats | 2 |
| `notify_session_error` — context and exception text | 1 |
| `notify_kill_switch` — path, context | 2 |
| `notify_risk_halt` — reason, context | 2 |
| `LiveRunner` — kill switch notification on trip | 1 |
| `LiveRunner` — kill switch notification only once | 1 |
| `LiveRunner` — no notification when switch clear | 1 |
| `LiveRunner` — risk halt notification | 1 |
| `LiveRunner` — risk halt notification only once | 1 |
| `LiveRunner` — no notification when healthy | 1 |
| `LiveRunner` — notifier exception does not crash runner | 1 |
| `LiveRunner` — notifier=None does not crash | 1 |

### No-real-network guarantee

`requests.post` is patched at the `packages.polymarket.notifications.discord`
module level in every test that touches HTTP.  No test contacts a real server.
`DISCORD_WEBHOOK_URL` is managed via `monkeypatch` in tests that check URL
resolution.

---

## 8. Non-goals

The following are explicitly out of scope for this spec:

- **Retries**: no retry logic; one attempt per event.
- **Message queuing**: no background thread, no queue; synchronous fire-and-forget.
- **Embeds or rich formatting**: plain markdown only; no Discord embed objects.
- **Alert routing or on-call**: not the responsibility of this module.
- **Multi-channel support**: single webhook URL only.
- **Rate limiting toward Discord API**: not implemented; gate events and kill-switch trips are rare enough that rate limits are not a concern.
- **Session start/stop hooks in CLI**: deferred; requires CLI session orchestration wiring.
- **WS reconnect error notifications**: deferred; requires ShadowRunner hook.
- **FastAPI or n8n forwarding**: deferred per SPEC-0012 §7 sequencing rule.
- **Telegram or alternative transports**: not a goal for Phase 1.

---

## References

- `packages/polymarket/notifications/discord.py` — implementation
- `tests/test_discord_notifications.py` — test coverage
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` §6 — canonical alerting requirement
- `docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md` — Req 9: Discord alerting
- `packages/polymarket/simtrader/execution/live_runner.py` — notifier integration
- `tools/gates/close_replay_gate.py`, `close_sweep_gate.py`, `run_dry_run_gate.py` — gate hooks
