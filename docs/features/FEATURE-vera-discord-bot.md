# Feature: Vera Discord Bot

**Status:** SHIPPED — Phase A (skeleton) + Phase B (approve/deny), live-verified 2026-06-02
**Type:** Operator tooling (Discord interaction surface)
**Decision:** [decision-retire-hermes-build-vera-bot](../obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md)
**Dev logs:** `docs/dev_logs/2026-06-02_vera-bot-phase-a-skeleton.md`, `docs/dev_logs/2026-06-02_vera-bot-phase-b-approvals.md`
**Phase detail docs:** [Phase A](vera_discord_bot_phase_a.md), [Phase B](vera_discord_bot_phase_b.md)

> **Naming — disambiguation.** "**Vera**" now means this **purpose-built
> discord.py bot**. It is **NOT** the retired `vera-hermes-agent` (the Hermes
> read-only Q&A agent, retired 2026-06-02 — see
> [vera-hermes-agent Operator Baseline](vera_hermes_operator_baseline.md),
> `status: retired`). The Hermes agent is gone (profile, gateway service, and the
> `polytool-status`/`-dev-logs`/`-files` skills removed); this bot reuses only the
> name. The separate, deferred *project-level* PolyTool→Vera rename is unrelated.

---

## Purpose

A small, always-on Discord bot that gives the operator **interactive** control
over the wallet-ingestion approval loop — specifically one-tap approve/deny of
pending wallets — which a webhook fundamentally cannot do.

### The split: webhook notifies, bot handles interaction

| Concern | Component | Why |
|---|---|---|
| **Notify** ("a wallet is pending") | Discord **webhook** (`DISCORD_WEBHOOK_URL`) — embed card + copy-block (see [Discord Alerting](FEATURE-discord-alerting-tracka.md)) | Always-on, bot-independent; a webhook can SEND embeds |
| **Interact** (approve/deny **buttons**) | This **bot** (`DISCORD_BOT_TOKEN`) via `/pending` | A webhook cannot RECEIVE `INTERACTION_CREATE`; only a bot can |

The two are deliberately decoupled — notifications never break if the bot is
down, and the copy-block + CLI gate remain the always-available fallback.

---

## Phase A — skeleton + `/ping` (SHIPPED)

Proves the connection, token, intents, and Docker always-on path.

- Package `packages/polymarket/discord_bot/` (`bot.py`, `config.py`, `__main__.py`).
- `VeraClient(discord.Client)` + `app_commands.CommandTree`. **Least-privilege
  intents**: only the non-privileged `guilds` intent (no message-content, no
  members).
- One command: **`/ping` → ephemeral `pong`**.
- Token from `DISCORD_BOT_TOKEN`, **fail-fast** if unset, **never logged**.
  Optional `DISCORD_GUILD_ID` → instant per-guild command sync.
- Docker: `Dockerfile.vera` (lean, non-root) + opt-in `vera-bot` compose service,
  `restart: unless-stopped` (long-lived, container `polytool-vera-bot`).
- Live-verified: bot online as `VERA#2261`, `/ping` → `pong`.

## Phase B — `/pending` + approve/deny buttons (SHIPPED, the first write surface)

The first Discord-triggered **write**, implemented as a **THIN TRIGGER** over the
Codex-verified `discovery review` CLI — the bot **never writes watchlist rows**;
`validate_transition` (inside the CLI) is the only writer.

- **`/pending`** (`packages/polymarket/discord_bot/approvals.py`): lists pending
  wallets reusing the exact webhook-path logic (`read_pending_candidates` +
  `_row_evidence` + `build_pending_embed` — same evidence as the webhook card),
  capped at 10 with an overflow note. Each card carries Approve (green) / Deny
  (red) buttons. **Only the operator can summon** `/pending`; the resulting cards
  are **public** in the channel (operator-requested 2026-06-02 — was ephemeral at
  ship; only the operator's clicks act).
- **Button handler**: defers within 3s → re-checks the author-guard → parses and
  re-validates the `custom_id` (`vera:<approve|deny>:<addr>`, address re-checked
  against `^0x[0-9a-fA-F]{40}$`) → reserves the wallet (idempotency) → runs
  `python -m polytool discovery review --approve/--deny <addr> … --json` via
  `asyncio.create_subprocess_exec` (**list-form, no shell**; ClickHouse password
  passed via the child env, never argv) → relabels the embed "Wallet
  approved/denied" and **disables both buttons** (success or stale). Never raises.
- **Idempotency**: an in-process `_actioned_wallets` reservation, taken
  synchronously and **never released** → at most one subprocess per wallet per
  process, so a double-click / approve-then-deny / concurrent clicks cannot
  double-write.

### Codex adversarial review — PASS (mandatory)

3 passes; all **10/10 invariants PASS**. Codex caught a real **blocking**
double-write race (the CLI doesn't reject re-actions) → fixed with the fail-safe
reservation above, re-reviewed to PASS.

### Live verification — PASSED (2026-06-02)

`/pending` rendered the 2 real pending cards; operator **approved** one
(`scanned→reviewed`, `review_status=approved`) and **denied** the other
(`review_status=rejected`) — both ClickHouse-verified, both gone from
`--list-pending`; every write went through the gate.

---

## Security boundaries

| Boundary | State |
|---|---|
| **Author-guard** | On BOTH `/pending` (summon) and every button click; `interaction.user.id == DISCORD_OPERATOR_USER_ID`. **Fail-closed** when unset (rejects everyone). A non-operator click → private "Not authorized", no write. |
| **Gate not bypassed** | Bot triggers the verified CLI; `validate_transition` is the only writer. No direct ClickHouse writes in the bot. |
| **Write scope** | ONLY `discovery review --approve/--deny <addr>`; argv hardcoded except the validated address + fixed action. No arbitrary CLI, no shell. |
| **Address** | Re-validated `^0x[0-9a-fA-F]{40}$`; truncated/garbage/whitespace/tampered → no subprocess. |
| **Secrets** | `DISCORD_BOT_TOKEN` + `CLICKHOUSE_PASSWORD` never logged, never on argv (password via child env). |
| **Denylist** | Untouched — the bot does not import/call kill_switch, execution, order placement, EIP-712/signing, risk_manager, the live bot, or config writers. |
| **Container least-privilege** | `vera-bot` gets only Discord vars + ClickHouse creds (explicit `environment:`, not `env_file`) — **no wallet `PK`, no CLOB secrets**. Read-only `artifacts` mount for display-time evidence. |

---

## Deployment

```bash
# .env (operator creates the Discord app + bot token + invite; Claude does not):
#   DISCORD_BOT_TOKEN=<token>            # never committed
#   DISCORD_GUILD_ID=<server id>         # instant command sync
#   DISCORD_OPERATOR_USER_ID=<user id>   # author-guard (fail-closed if unset)
#   CLICKHOUSE_PASSWORD=<...>            # for /pending read + review trigger
docker compose --profile vera-bot up -d --build vera-bot
docker compose logs -f vera-bot          # "Vera is online ...", commands synced
```

Opt-in profile `vera-bot`; long-lived (`restart: unless-stopped`); exposes no
ports (outbound gateway connection only). Image: `Dockerfile.vera`.

---

## Known residual

An approve/deny performed via the **CLI outside the bot process** is not
reflected in the bot's in-process idempotency guard. Fully closing this needs
CLI-level idempotency (reject non-pending re-actions) — a follow-up for the
`discovery review` CLI owner, out of scope for this thin-trigger bot. Every write
still passes through the gate, so the residual is at worst a duplicate *valid*
write, never a bypass.

## Tests

`tests/test_vera_discord_bot.py` (12) + `tests/test_vera_approvals.py` (40) —
all offline (`pytest.importorskip("discord")`). Cover token fail-fast, intents,
custom_id parse/build, list-form argv (no password on argv), author-guard,
handler paths (non-operator/malformed/tampered → no subprocess; success disables
+ relabels; idempotency duplicate/concurrent/fail-safe; deferred-first; never
raises), and `/pending` (public cards, cap+overflow, non-operator rejected).
