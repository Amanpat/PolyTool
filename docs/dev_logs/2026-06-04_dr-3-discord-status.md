# DR-3 — Discord `/status` Window (read-only)

Date: 2026-06-04
Packet: `work-packet-dr-3-discord-status`
Mode: build. New code + tests only. No DB writes, no lifecycle changes, no commits.

## Objective

On-demand, read-only `/status` slash command on the Vera gateway bot. Shows a
live scan-status window (health line, metric tiles, top-N by realized PnL with
wallet ID and username as separate columns, throughput footer). Operator-only
invocation (author-guard); card posts publicly within the private channel.

## What was built

- `packages/polymarket/discord_bot/status_window.py` (NEW) — the pure, testable
  assembler. One injectable `QueryRunner` is the only ClickHouse touch point.
  - Counts: `in_queue` (scan_queue pending+leased), `failed` (scan_queue failed),
    `pending_review` (candidate-tier filter, same as `read_pending_candidates`,
    with pre-migration fallback), `scanned_today` (watchlist last_scanned_at on
    today() UTC).
  - Top-N: `argMax(realized_pnl, computed_at)` over `user_pnl_bucket` (bucket_type
    `day`) LEFT JOIN latest `leaderboard_snapshots.username` per wallet — wallet
    ID and username are SEPARATE dataclass fields / embed columns.
  - Health: `last_drain_at` (max updated_at over done/failed/leased queue items).
  - Footer best-effort: `ris_docs_today` probes `polytool.ris_documents`; returns
    None gracefully if the table is absent (canonical RIS store is SQLite, no
    guaranteed cheap CH count — omitted per packet).
  - `build_status_embed()` renders the embed dict (discord.Embed.from_dict
    compatible). Missing data renders an em-dash, never a fabricated 0.
- `packages/polymarket/discord_bot/status_command.py` (NEW) — thin Discord handler.
  Author-guard via the SHIPPED `approvals.is_operator` (commit c66f375). Public
  deferral + single embed edit. NO buttons, NO subprocess, NO writer import.
- `packages/polymarket/discord_bot/bot.py` — registered `/status` (lazy import of
  the handler, mirroring `/pending`).
- `tests/test_status_window.py` (NEW) — 16 assembler/handler tests.
- `tests/test_vera_discord_bot.py` — updated the registered-command assertion to
  `["pending", "ping", "status"]`.

## Definition of Done — per-item status (evidence-gated)

### DONE — `/status` returns the card with correct queue/scanned/pending/failed counts on seeded data

`test_assemble_counts_on_seeded_data`: seeded queue buckets (pending 7, leased 2,
failed 3, done 40), pending=5, scanned_today=12 →
`in_queue==9`, `failed==3`, `pending_review==5`, `scanned_today==12`, `degraded==[]`.
`test_pending_review_falls_back_when_tier_columns_absent` covers the
pre-migration fallback. `test_embed_metric_tiles_present` confirms all four tiles
render.

### DONE — Top-N by realized PnL renders with wallet ID and username in separate columns

`test_top_wallets_preserve_descending_order` (PnL `[1.5m, 24k, -350]` descending),
`test_top_wallet_id_and_username_are_separate_fields` (distinct dataclass fields;
a wallet without a snapshot username → `None`),
`test_embed_renders_wallet_id_and_username_in_separate_columns` (three inline
fields "Wallet ID" / "Username" / "Net PnL"; username does NOT appear in the
Wallet ID column and the missing username renders an em-dash in the Username
column).

### DONE — Non-operator invocation is ignored/denied (author-guard); operator invocation works

`test_non_operator_status_is_denied_and_reads_nothing` — non-operator gets
ephemeral "Not authorized.", the reader is NEVER called, and `defer` is never
awaited (the guard fires before any read).
`test_unset_operator_denies_everyone` — fail-closed (unset operator id authorizes
no one). `test_operator_status_posts_public_card` — operator gets a public
deferral (`thinking=True`) and a single embed edit with NO `view`/buttons.

### DONE — No write/mutation path exists in the command

`test_assembler_emits_only_select_statements` — every SQL the assembler builds
starts with SELECT and contains no INSERT/ALTER/UPDATE/DELETE/DROP/CREATE/TRUNCATE
statement keyword. The handler has no subprocess and no writer import. Confirmed
by code: `status_window` imports only stdlib + dataclasses; `status_command`
imports `is_operator`, `BotConfig`, and the read-only assembler. (See "No write
surface" below.)

### BLOCKED — Live-verified in the channel

Cannot be done in this environment: requires a running gateway process plus the
`DISCORD_BOT_TOKEN` operator secret (and a live ClickHouse with seeded data).
Operator steps to verify:

1. Ensure `.env` has `DISCORD_BOT_TOKEN`, `DISCORD_OPERATOR_USER_ID`,
   `DISCORD_GUILD_ID`, and `CLICKHOUSE_PASSWORD` (+ `CLICKHOUSE_HOST`/`PORT`/`USER`
   if not localhost defaults).
2. Start the gateway (Vera bot): `python -m polytool` is not the entry — run the
   bot module entry (`packages.polymarket.discord_bot.bot.run`) however the
   gateway service is wired (e.g. the vera-bot compose service / Dockerfile.vera),
   or via the systemd unit (see env-hygiene note below).
3. The bot syncs commands per-guild instantly when `DISCORD_GUILD_ID` is set.
4. In the private channel, run `/status` as the operator → a public status card
   should appear with the four tiles + Top-N (wallet ID / username / net PnL).
5. Run `/status` as the other (non-operator) member → expect a private
   "Not authorized." and NO public card.

## Test evidence

Command:

```
python -m pytest tests/test_vera_discord_bot.py tests/test_vera_approvals.py \
  tests/test_wallet_ingestion_notify.py tests/test_status_window.py --tb=short -q
```

Result: **128 passed, 0 failed, 0 skipped** (1 warning: unrelated `audioop`
deprecation from discord.py on Python 3.12).

Broader related subset (added two-tier + discord-notifications):

```
python -m pytest tests/test_status_window.py tests/test_vera_discord_bot.py \
  tests/test_vera_approvals.py tests/test_wallet_ingestion_notify.py \
  tests/test_wallet_discovery_two_tier.py tests/test_discord_notifications.py --tb=short -q
```

Result: **202 passed, 0 failed, 0 skipped** (1 warning).

CLI import smoke: `python -m polytool --help` loads with no import errors.

Known pre-existing RIS academic-ingest failures: NOT surfaced by this run (those
suites were not in scope of the focused subset; this packet added no new failures).

## No write surface (read-only confirmation)

- `status_window.py`: the only DB interface is `_ch_select` — HTTP **GET** with
  `FORMAT JSONEachRow`. Every SQL it constructs is a SELECT (proven by
  `test_assembler_emits_only_select_statements`). No INSERT, no ALTER, no
  `_post_jsonl` import, no subprocess. `read_status_snapshot` fail-fasts on an
  unset `CLICKHOUSE_PASSWORD` (no hardcoded fallback) per the CLAUDE.md auth rule.
- `status_command.py`: author-guard → read → post embed. No `ApproveDenyView`, no
  buttons, no `run_review_cli` / subprocess, no writer import. The reader is
  injectable and defaults to the read-only snapshot reader.
- Denylist untouched: nothing here imports kill_switch / execution / order
  placement / EIP-712 signing / risk_manager / the live bot.

Per Acceptance Gate 1, Codex adversarial review is NOT required for this
read-only command.

## Env-hygiene operator note (reviving the gateway for `/status`)

This is operator guidance, not code — capture it so reviving the gateway does not
re-hit the 6/2 environment loop:

- Use a **current** gateway model — NOT the retired `gemini-2.0-flash-001`.
- Skills live in the **profile dir** (not the repo).
- Restart the gateway with:
  `systemctl --user restart hermes-gateway.service`
  then **force a snapshot re-index** so the new command set is picked up.
- Required env for `/status`: `DISCORD_BOT_TOKEN`, `DISCORD_OPERATOR_USER_ID`
  (fail-closed — unset = nobody authorized), `DISCORD_GUILD_ID` (instant per-guild
  command sync), and `CLICKHOUSE_PASSWORD` (+ host/port/user if not localhost).

## Files changed (uncommitted)

- `packages/polymarket/discord_bot/status_window.py` (new)
- `packages/polymarket/discord_bot/status_command.py` (new)
- `packages/polymarket/discord_bot/bot.py` (register `/status`)
- `tests/test_status_window.py` (new)
- `tests/test_vera_discord_bot.py` (command-set assertion updated)
- `docs/dev_logs/2026-06-04_dr-3-discord-status.md` (this file)

## Ready-to-paste state summary (orchestrator consolidates CURRENT_STATE/CURRENT_DEVELOPMENT)

```
DR-3 Discord /status window: shipped (uncommitted). Read-only operator-only
slash command on the Vera gateway — health line + four tiles (in-queue, scanned
today, pending review, failed) + Top-N by realized PnL (argMax over
user_pnl_bucket) with wallet ID and username as separate columns. Assembler in
status_window.py (injectable QueryRunner, SELECT-only, fail-fast on
CLICKHOUSE_PASSWORD); thin handler in status_command.py reuses the shipped
author-guard. 128/202 focused tests pass; no new failures. No write surface.
Live-verify in channel is BLOCKED on a running gateway + DISCORD_BOT_TOKEN.
```
