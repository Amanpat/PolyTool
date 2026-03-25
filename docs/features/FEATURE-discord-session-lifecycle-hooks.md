# Feature: Discord Session Lifecycle Hooks

**Spec**: `docs/specs/SPEC-0015-discord-alerting-and-operator-notifications.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Finishes the deferred Discord lifecycle wiring for `simtrader live` so
session start, clean stop, and session error notifications fire from the CLI
boundary instead of being left as uncalled helpers.

### Key changes

1. `tools/cli/simtrader.py` now loads the Discord notifier once for the live
   CLI session boundary and passes it into `LiveRunConfig`.
2. `_live()` fires `notify_session_start()` immediately before `run_once()`.
3. `_live()` fires `notify_session_stop()` after a clean `run_once()` result,
   using the returned summary payload.
4. `_live()` fires `notify_session_error()` when `run_once()` raises a session
   `RuntimeError`.
5. All lifecycle calls are wrapped in a local fail-safe helper, so Discord
   transport failures never change the CLI exit path.

---

## Changed files

| File | Change |
|------|--------|
| `tools/cli/simtrader.py` | Added safe Discord notifier loading, CLI lifecycle hook dispatch, and notifier injection into `LiveRunConfig` |
| `tests/test_discord_notifications.py` | Added CLI lifecycle coverage for start, stop, error, and non-fatal notifier failures |
| `docs/dev_logs/2026-03-08_discord_session_lifecycle_hooks.md` | Records the implementation and test evidence for the CLI lifecycle hook patch |

---

## Deferred

- `ShadowRunner` / WS reconnect lifecycle errors are still deferred.
- Discord remains a thin transport only: no retries, queueing, or ack logic.
