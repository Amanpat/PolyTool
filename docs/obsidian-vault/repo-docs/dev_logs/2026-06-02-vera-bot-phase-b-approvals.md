---
title: Vera Bot Phase B Approvals
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_vera-bot-phase-b-approvals.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — Vera bot Phase B: /pending + approve/deny buttons (first write surface)

**Date:** 2026-06-02
**Slug:** vera-bot-phase-b-approvals
**Type:** Feature (first Discord-triggered write; security-critical)
**Decision record:** `docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`
**Predecessor:** `docs/dev_logs/2026-06-02_vera-bot-phase-a-skeleton.md`

## Objective

Add the first Discord-triggered write: one-tap approve/deny of pending wallets.
Ratified approach: the bot is a **THIN TRIGGER** over the already-Codex-verified
`discovery review` CLI — it does NOT reimplement the lifecycle gate. The webhook
(WP-2) stays as notifier + copy-block fallback; no buttons on the webhook card.

## What was built

### `packages/polymarket/discord_bot/approvals.py` (the write surface)

- **`/pending`** (operator-only, ephemeral): lists pending wallets reusing the
  exact webhook-path logic — `read_pending_candidates` (read-only) + `_row_evidence`
  + `build_pending_embed` (same evidence card). One ephemeral message per wallet,
  capped at 10 with a "+K more — action these first." note. Each card carries an
  Approve (green) / Deny (red) action row.
- **Button handler** (the mutation path), in order:
  1. **Defer within 3s** (deferred message UPDATE) — the subprocess outlasts the ack window.
  2. **Author-guard again** — `interaction.user.id == DISCORD_OPERATOR_USER_ID`, else ephemeral "Not authorized" + log.
  3. **Parse + re-validate** the `custom_id` (`vera:<approve|deny>:<addr>`); address re-checked against `^0x[0-9a-fA-F]{40}$` (whitespace rejected). Any failure → ephemeral error, NO subprocess.
  4. **Idempotency reservation** (`_actioned_wallets`, taken synchronously before the subprocess, never released — see below).
  5. **Subprocess** `python -m polytool discovery review --approve/--deny <addr> --clickhouse-host … --json` via `asyncio.create_subprocess_exec` (list-form, no shell; address is one argv element; the ClickHouse password is passed via the child env, never argv).
  6. **Outcome:** rc==0 → relabel the embed "Wallet approved/denied" + disable both buttons; rc!=0 → disable buttons + ephemeral "could not confirm / already actioned, re-check with --list-pending". Never raises (catch-all).
- The bot **NEVER** writes watchlist rows — `validate_transition` inside the CLI is the only writer.

### `config.py`

`BotConfig`/`ClickHouseConfig` from env. `DISCORD_OPERATOR_USER_ID` is the
author-guard; **fail-closed** when unset (rejects everyone). The bot token and
ClickHouse password are read at point-of-use, never stored on the config object.

### `bot.py` / container

- Registers `/pending` alongside `/ping`; config-driven client construction.
- `docker-compose.yml` `vera-bot`: adds `DISCORD_OPERATOR_USER_ID` + ClickHouse
  creds (host=`clickhouse`, port, user, password) + a **read-only** `artifacts`
  mount (so `/pending` shows the same display-time evidence the webhook does) +
  `depends_on: clickhouse`. Still least-privilege explicit env — **no PK/CLOB**
  secrets in the bot container.
- `.env.example` documents `DISCORD_OPERATOR_USER_ID`.

### Idempotency design (the hard part — see Codex below)

`_actioned_wallets` is an in-process set. The reservation is taken **synchronously**
(no `await` between the membership check and the add) so concurrent clicks on the
single asyncio loop can't both spawn a subprocess, and it is **never released** —
at most one subprocess per wallet per process. This is deliberately fail-safe: a
non-zero CLI result does not reliably mean "no write happened" (a transport
timeout *after* ClickHouse accepts the insert reports failure), so releasing
could double-write. Trade-off: a genuinely-failed attempt isn't retried by the bot
in-session — the operator retries via the CLI copy-block or restarts the bot.

## Codex adversarial review (MANDATORY — done)

Ran `codex exec -m gpt-5.4` adversarially against the 10 packet criteria, three passes:

1. **Pass 1:** 9/10 PASS; **invariant 4 FAIL (blocking)** — the verified CLI
   doesn't reject a re-action, so double-click / approve-then-deny could double-write
   (last-writer-wins). Other 9 (author-guard both surfaces, address re-validation,
   action-set constraint, list-form subprocess, gate-not-bypassed, no secret in
   argv/logs, buttons disabled, deferred <3s, no raise) all PASS.
2. **Fix 1** (`cc66272`): in-process reservation with synchronous reserve; released
   on failure. **Pass 2:** still FAIL — releasing on `rc!=0` is unsafe (ambiguous
   transport failure after a real write).
3. **Fix 2** (`02120ae`): reserve once, **never release** (fail-safe). **Pass 3:
   invariant 4 PASS** within single-process scope. Only residual: an approve/deny
   run via the CLI *outside* the bot process (documented; needs CLI-level
   idempotency — a follow-up for the CLI owner, out of this bot packet's scope).

Final Codex verdict: all 10 invariants PASS.

## Tests — `tests/test_vera_approvals.py` (40, offline) + updated skeleton (12)

custom_id parse/build (garbage/tampered/whitespace rejected); argv list-form +
no-password-on-argv + bad-action/bad-address raise; `run_review_cli` exec uses env
not argv; author-guard (operator/other/unset); handle_action paths (non-operator
no subprocess, malformed/tampered no subprocess, approve/deny success disables +
relabels, stale → already-actioned, runner raises caught, deferred first);
idempotency (duplicate-click no second write, failure keeps reservation no
double-write, concurrent clicks → single subprocess); /pending (non-operator no
read, empty, read-failure, one-card-per-wallet ephemeral, cap-10 + overflow).

## Verification

**Offline (done):** 52 Vera tests pass; full-suite collection 5530 (no import
breakage); 387 discovery/approval tests still green; `python -m polytool --help`
OK; `docker compose --profile vera-bot config` shows only Discord + ClickHouse
vars (no PK/CLOB). Codex: all 10 invariants PASS.

**Live (CONFIRMED 2026-06-02):** operator set `DISCORD_OPERATOR_USER_ID`, bot
rebuilt + online (`VERA#2261`, commands synced). Verified against the 2 real
pending wallets:

- `/pending` (operator) rendered both pending cards with Approve/Deny.
- **Approve** `0xcf60…6f5` → `scanned → reviewed`, `review_status=approved`
  (ClickHouse-verified).
- **Deny** `0x84cf…f63` → `review_status=rejected`, lifecycle stays `scanned`
  (ClickHouse-verified).
- `discovery review --list-pending` afterwards → **count 0** (both gone).
- The exact gate transitions prove every write went through `validate_transition`
  (the bot never wrote rows directly). Bot logs clean — no unauthorized /
  malformed / non-zero lines.

Both approve and deny paths confirmed end-to-end through the real CLI/gate.
(Optional operator-id-mismatch live test skipped — the author-guard is
Codex-verified + unit-tested.)

**Presentation change (operator-requested, post-verify):** `/pending` cards were
made PUBLIC (visible to the whole channel) instead of ephemeral. Only the operator
can summon the list, and the per-click author-guard remains the write access
control (a non-operator click → private "Not authorized", no write). The
security-critical `handle_action` write path is byte-for-byte unchanged, so the
Codex-verified write invariants still hold; only the read/list presentation
changed. Tradeoff: pending wallet addresses + (public) evidence are now visible
server-wide.

## Guards honored

Denylist untouched (no kill_switch / execution / order placement / signing /
risk_manager / live bot / config writers). Secrets via env, never logged or on
argv. Full-address regex. Author-guard on BOTH /pending and the button click.
Webhook path unaffected.
