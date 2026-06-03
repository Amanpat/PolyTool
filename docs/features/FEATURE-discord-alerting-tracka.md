# Feature: Discord Alerting — Track A

**Status:** SHIPPED (extended 2026-06-02 with the pending-review embed-card system)
**Spec:** [SPEC-0015](../specs/SPEC-0015-discord-alerting-and-operator-notifications.md)

> **Notifier vs. bot (read this first).** The Discord **webhook** is the
> always-on **notifier** — it posts alerts and pending-review cards and never
> depends on a bot being up. The fenced **copy-block** in each pending card is
> the **bot-independent fallback** (one-tap copy of the approve/deny CLI
> commands; always works). **Interactive** one-tap approve/deny *buttons* are a
> separate component — the **Vera discord.py bot** (see
> [FEATURE-vera-discord-bot](FEATURE-vera-discord-bot.md)). A webhook can SEND
> embeds but cannot RECEIVE button interactions, which is exactly why
> interaction lives in the bot while notification stays in the webhook. The two
> are decoupled by design: notifications never break if the bot is down.

---

## Summary

Thin, testable Discord webhook notification layer for PolyTool operator alerts.
Covers (a) gate pass/fail and live-runner kill-switch / risk-halt events, and
(b) the wallet **pending-review embed cards** (WP-1/WP-2, 2026-06-02). All
delivery is via the outbound `DISCORD_WEBHOOK_URL`; the layer is stateless and
never raises.

---

## What was built

### New module: `packages/polymarket/notifications/discord.py`

Stateless transport layer.  All functions return `bool` and never raise.

| Function | Purpose |
|----------|---------|
| `post_message(text="", *, embeds=None, webhook_url=None)` | Core transport — posts content and/or embeds in one webhook call (content-only stays back-compatible; empty payload → no HTTP, returns False) |
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

## Wallet pending-review notifications (WP-1 + WP-2, 2026-06-02)

When the wallet-ingestion worker advances a candidate to
`review_status='pending'`, the operator is notified via a Discord **embed card**
posted through the same outbound webhook. This is the notification half of the
operator approval loop; the action half is the CLI gate (`discovery review
--approve/--deny`) and/or the Vera bot's buttons.

### WP-1 — richer evidence fields (data layer)

`packages/polymarket/discovery/evidence_summary.py` +
`tools/cli/wallet_scan.py` surface three additional, display-time evidence
fields (computed from the wallet's fresh scan data, not the stored `reason`):

- **Open vs. resolved split** — `N open / M resolved` (from `outcome_counts`;
  PENDING vs. the four resolved buckets; UNKNOWN_RESOLUTION excluded).
- **Discovery source** — humanized from the watchlist row: `loop_a` →
  "leaderboard discovery", `manual` → "manual", `loop_d` → "CLOB anomaly".
- **Category focus** — dominant *known* category (omitted entirely when the
  wallet is uncategorised; never fabricated).

A row carrying only provenance (`source`) falls back to the stored reason rather
than presenting bare provenance as performance evidence.

### WP-2 — embed card + digest + copy-block

`packages/polymarket/discovery/pending_notify.py` builds the notification:

- **Single card** (`build_pending_embed` + `build_single_content`): info-blue
  embed (`0x3498DB` = review *severity*, not wallet quality), title "Pending
  wallet review", full address in the description, fields **PnL / Win rate /
  Trades / CLV / Positions (open/resolved) / Discovery / Category** (Category
  only when present; Win rate `-` when there is no resolved book). Footer
  "PolyTool - Vera".
- **Copy-block** in the message **content** — a fenced ```` ``` ```` block with
  the full-address `discovery review --approve/--deny` commands. This is the
  reliable one-tap-copy affordance and the **bot-independent fallback**.
- **Digest** (`build_digest_embed` + `build_digest_content`): >1 unnotified
  candidate collapses into ONE message (one stacked field per wallet + a
  copy-block per wallet), bounded by `_DIGEST_MAX=10` and an 1800-char content
  budget; overflow is reported (`skipped_capped`), never silently dropped.
- **Dedup**: candidates are notified exactly once via the WI-5
  `approvals_notified.json` state file; a wallet is marked notified only on a
  delivered send (a failed webhook re-notifies next pass). The whole pass is
  non-fatal — a webhook failure never blocks the ingestion pipeline.

`notify_pending_candidates(rows)` returns
`{considered, posted, deduped, failed, mode[, skipped_capped]}` and is fired
(non-fatally) at the end of `discovery run-worker`.

**Buttons are intentionally NOT on the webhook card** — a webhook cannot receive
component interactions. Interactive approve/deny lives in the Vera bot's
`/pending`; see [FEATURE-vera-discord-bot](FEATURE-vera-discord-bot.md).

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
