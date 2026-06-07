---
type: decision
status: accepted
source_zone: claude_memory
last_updated: 2026-06-02
lifecycle: active
tags: [decision, vera, hermes, discord, operator-tooling, bot]
---

# Decision: Retire Hermes, build our own Discord bot ("Vera")

**Date:** 2026-06-02
**Status:** Accepted (operator)

## Decision
Retire the `vera-hermes-agent` (Hermes) operator agent. Build a purpose-built discord.py bot that reuses the name **Vera**. Add real one-tap approve/deny buttons — now possible because a bot (unlike a webhook or Hermes) can receive `INTERACTION_CREATE` events.

## Why
- Hermes's entire feature set was **read-only natural-language Q&A over repo docs** (3 skills: polytool-status / dev-logs / files) on a weak, rate-limited free model (deepseek-v3.2 / Ollama Cloud 429s).
- Those features are redundant: notifications → webhook (shipped); live metrics → Grafana; deep reasoning → Claude / Claude Code (already in the loop, far stronger than deepseek).
- Hermes **cannot** do the one future feature actually wanted (buttons) — a button click is a structured interaction needing an always-on listener; Hermes is text-only. So "keep Vera for future Discord work" rested on a false premise: Hermes was a detour, not the road to interactivity.
- Hermes is isolated and read-only (no trading, no jobs, nothing operational depends on it) → removal is low-risk.
- A single discord.py bot is the real path: it can do interactive buttons AND (optionally, later) deterministic status/dev-log slash commands, more reliably than Hermes, with no flaky free LLM.

## Architecture (recommended)
- **Webhook stays** as the notifier + copy-block fallback (always works, bot-independent).
- **Bot adds interaction on top:** a `/pending` slash command lists pending wallets with approve/deny **buttons**. Keeps notification (webhook) decoupled from interaction (bot) — avoids webhook/bot double-post coordination.
- Button handler is the first Discord-triggered **write** surface: author-ID guarded (only operator's Discord user ID), routes through the existing enforced gate (`validate_transition` via the `discovery review` path) — NEVER writes the watchlist directly, idempotent (gate rejects invalid transitions / already-actioned), defers within 3s, disables buttons after action. Scoped to approve/deny ONLY — denylist (trading / kill_switch / execution / risk_manager / secrets / config) untouched. Codex adversarial review MANDATORY.
- Token via `.env` (`DISCORD_BOT_TOKEN`); operator creates the Discord app + token + invite (Claude does not). Deployment: Docker (deployment standard); buttons work when the bot is up, copy-block is the always-available fallback.

## Build phases
- **Phase A** — bot skeleton in Docker: connects, one trivial slash command (`/ping`), verify token/intents/always-on. No writes.
- **Phase B** — `/pending` + approve/deny buttons routed through the gate. Codex-reviewed, live-verified.
- **Optional later** — read-only status/dev-logs/files slash commands (only if Discord queries are actually wanted; Claude/CC already cover this).

## Naming note
"Vera" now = the new discord.py bot (Hermes agent retired, name freed). The separate, deferred **project-level** PolyTool→Vera rename is unaffected and still deferred — be aware of the overlap.

## Supersedes / relates
- Refines [[decision-discord-approval-descope-v1|Discord approval descope]] (webhook + CLI was v1; the bot is the interactive successor).
- WP-2 (webhook embed card) is unaffected — pure webhook, no Hermes.

## Cross-References
- [[2026-05-31-wallet-ingestion-sprint-completion|Wallet ingestion sprint completion]]
- [[decision-discord-approval-descope-v1|Discord approval descope v1]]

## Connections
- [[index|Vault Home]]


---

## Implementation progress (2026-06-02)

**Hermes RETIRED + committed (3dbf1cd).** systemd user service stopped/disabled/unit-deleted (confirmed absent); `hermes profile delete` removed the profile dir + 76 skills/config/keys + the alias binary (only `default` remains); repo wiring removed (`skills/polytool-operator/`, healthcheck + test scripts); 4 feature docs + INDEX rows marked retired (history preserved); CURRENT_STATE/CURRENT_DEVELOPMENT updated (stale WP7-Hermes path voided); operational scan confirmed nothing depends on it. Extra dead file `scripts/start_vera_discord_gateway.sh` also removed (flagged, not silent). Webhook notification path untouched. Minor: a now-stale "Vera/Hermes gateway" comment remains in `pending_notify.py:32` — cosmetic, optional fix.

**Vera bot Phase A LIVE + committed (16fa5b1 + build/intent fixes).** discord.py bot in Docker (`polytool-vera-bot`, restart: unless-stopped), online as VERA#2261, slash commands synced to guild, token never printed, least-privilege intents (guilds only; message-content + members OFF). `/ping` awaiting operator confirm.

**Phase B (buttons) — recommended execution path (packet HELD).** Bot validates author Discord ID + full-address regex, then triggers the ALREADY-CODEX-VERIFIED `discovery review --approve/--deny` CLI via list-form subprocess (no shell) → gate stays in one audited place, bot is a thin trigger. Blast radius: bot container gains ClickHouse access (needed to action the watchlist) — ACCEPTED: action is low-stakes watchlist approve/deny only, author-guarded, denylist (kill_switch/execution/risk_manager/trading/signing/config) untouched. Codex adversarial review mandatory. Packet held until `/ping` confirms + approach ratified.


**Update (2026-06-02):** Phase A `/ping` CONFIRMED (pong received) — skeleton verified. Phase B packet issued using the subprocess-CLI-trigger approach (operator did not object). Sequence: Codex adversarial review FIRST, then operator live-verify. Phase B is the first Discord-triggered write surface.
