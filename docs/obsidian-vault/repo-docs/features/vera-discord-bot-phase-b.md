---
title: Vera Discord Bot Phase B
type: reference
status: complete
completed: 2026-06-02
track: operator-tooling
scope: write (approve/deny only)
phase: B
codex_review: PASS (10/10 invariants)
live_verified: 2026-06-02 (approve + deny end-to-end through the gate)
source_zone: repo
mirror_of: docs/features/vera_discord_bot_phase_b.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Feature: Vera Discord Bot — Phase B (/pending + approve/deny buttons)

The first Discord-triggered **write**: one-tap approve/deny of pending wallets.
The bot is a **THIN TRIGGER** over the Codex-verified `discovery review` CLI — it
never writes watchlist rows; `validate_transition` (inside the CLI) is the only
writer. The webhook (WP-2) remains the notifier + copy-block fallback; the buttons
live only on `/pending`, never on the webhook card.

Decision record:
`docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`.

## What Was Built

| Item | Detail |
|---|---|
| `/pending` | Operator-only summon; cards are PUBLIC (operator-requested). Lists pending wallets (cap 10 + overflow note), reusing `read_pending_candidates` + `_row_evidence` + `build_pending_embed` — same evidence as the webhook. Each card has Approve/Deny buttons; only the operator's clicks act (author-guard). |
| Button write | Defer <3s → author-guard → parse+re-validate custom_id (`^0x[0-9a-fA-F]{40}$`) → idempotency reserve → `discovery review --approve/--deny <addr>` via `asyncio.create_subprocess_exec` (list-form, no shell; password via child env). |
| Idempotency | `_actioned_wallets` reserved synchronously, never released → at most one subprocess per wallet per process (fail-safe vs. ambiguous CLI failures). |
| Author-guard | `DISCORD_OPERATOR_USER_ID` on BOTH `/pending` and every click; fail-closed when unset. |
| Container | `vera-bot` compose service gains ClickHouse creds + operator id + read-only `artifacts` mount + `depends_on: clickhouse`. Least-privilege (no PK/CLOB). |
| Tests | `tests/test_vera_approvals.py` (40 offline) + updated skeleton (12). |
| Codex | 3 adversarial passes; all 10 invariants PASS (invariant 4 fixed twice). |

## Security Boundaries

| Boundary | State |
|---|---|
| Write scope | ONLY `discovery review --approve/--deny <addr>`; hardcoded argv except validated address + fixed action |
| Direct DB writes | None — the CLI's `validate_transition` is the sole writer |
| Author-guard | Both list + click; fail-closed when `DISCORD_OPERATOR_USER_ID` unset |
| Address | Re-validated `^0x[0-9a-fA-F]{40}$`; whitespace/garbage/tampered rejected, no subprocess |
| Subprocess | `create_subprocess_exec` list-form, never shell; password via env, never argv |
| Double-write | Prevented in-process (synchronous reserve, never released) |
| Secrets | Token + ClickHouse password never logged or on argv (even error paths) |
| Container secrets | Only Discord + ClickHouse vars; no wallet (PK) / CLOB secrets |
| Denylist | Untouched (kill_switch / execution / signing / risk_manager / live bot / config writers) |

## Known Residual

An approve/deny performed via the **CLI outside the bot process** is not reflected
in the bot's in-process guard. Fully closing this needs CLI-level idempotency
(reject non-pending re-actions) — a follow-up for the `discovery review` CLI
owner, out of scope for this thin-trigger bot. Single trusted operator; every
write still passes through the gate, so the residual is a duplicate valid write,
never a bypass.

## Run / Verify

```bash
# .env: DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_OPERATOR_USER_ID (your user ID),
#       CLICKHOUSE_PASSWORD. Then:
docker compose --profile vera-bot up -d --build vera-bot
docker compose logs -f vera-bot     # "Vera is online", commands synced
# In Discord (as the operator): /pending -> approve one / deny another.
# Confirm: python -m polytool discovery review --list-pending  (actioned wallet gone)
```

## Related Files

- `packages/polymarket/discord_bot/approvals.py` — the write surface
- `packages/polymarket/discord_bot/config.py`, `bot.py`
- `Dockerfile.vera`, `docker-compose.yml` (`vera-bot`)
- `tests/test_vera_approvals.py`
- `docs/dev_logs/2026-06-02_vera-bot-phase-b-approvals.md`
