# Dev Log: Discord Alerting — Track A

**Date:** 2026-03-08
**Branch:** simtrader
**Spec:** SPEC-0015

---

## What was built

Implemented the Discord alerting layer described in SPEC-0013 Packet 4.

### New files

| File | Purpose |
|------|---------|
| `packages/polymarket/notifications/__init__.py` | Package init |
| `packages/polymarket/notifications/discord.py` | Transport module — 7 public functions, all `bool` return, never raise |
| `tests/test_discord_notifications.py` | 29 offline tests covering transport, formatters, and LiveRunner hooks |
| `docs/specs/SPEC-0015-discord-alerting-and-operator-notifications.md` | Full spec: taxonomy, contract, failure behavior, test strategy |
| `docs/features/FEATURE-discord-alerting-tracka.md` | Feature summary |

### Modified files

| File | Change |
|------|--------|
| `tools/gates/close_replay_gate.py` | Added `notify_gate_result()` call inside `_write_gate_result()` |
| `tools/gates/close_sweep_gate.py` | Same |
| `tools/gates/run_dry_run_gate.py` | Same |
| `packages/polymarket/simtrader/execution/live_runner.py` | Added `notifier` field to `LiveRunConfig`; kill-switch and risk-halt hooks in `run_once()` |
| `pyproject.toml` | Added `packages.polymarket.notifications` to setuptools packages |
| `.env.example` | Added `DISCORD_WEBHOOK_URL` entry |

---

## Design decisions

**Notification in `_write_gate_result()` helper**: each gate script has a
local `_write_gate_result()` function that is called on every exit path.
Adding the notification there covers all pass and fail paths with a single
edit point per script.

**Duck-typed `notifier` on `LiveRunConfig`**: avoids a hard import of the
discord module in the execution layer.  The discord module itself satisfies
the protocol (module-level functions act as callables on the duck-typed
object).  Tests pass `MagicMock()`.

**Fire-once flags on `LiveRunner`**: `_kill_switch_notified` and
`_risk_halt_notified` prevent alert floods if the session loop keeps calling
`run_once()` after a persistent fault.

**Session lifecycle deferred**: `LiveRunner.run_once()` is a single-tick
method.  Session start/stop events require the CLI session loop.  Functions
`notify_session_start/stop/error` are implemented and tested; only the CLI
call sites are missing.

---

## Test results

```
29 passed, 0 failed  (tests/test_discord_notifications.py)
1364 total passing  (full suite, excluding 7 pre-existing failures in
                     test_gate2_eligible_tape_acquisition.py)
```

---

## What remains before Discord is fully operational for Stage 0

1. **Set `DISCORD_WEBHOOK_URL`** in your `.env` file.
2. **Run any gate script** (e.g. `python tools/gates/run_dry_run_gate.py`) and
   confirm a notification arrives in Discord — this is the Stage 0 verification
   step per SPEC-0012 §8.
3. **Wire session start/stop to CLI** — add `notify_session_start()` and
   `notify_session_stop()` calls to the `simtrader live` session loop in
   `tools/cli/simtrader.py`.
4. **Wire session error / WS reconnect** — add `notify_session_error()` to
   exception handlers in the shadow runner and live CLI session loop.

Items 3 and 4 are deferred to a follow-on integration task; they do not block
the Stage 0 gate prerequisite (alerts wired and confirmed active) since gate
notifications are fully wired.
