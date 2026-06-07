# 2026-06-02 — WP-2: Pending-review embed card via webhook (copy-block, no buttons)

## Objective

Final notification-UI build for wallet pending review. Replace the plain-text
notification with a Discord **embed card** sent through the EXISTING outbound
webhook (`DISCORD_WEBHOOK_URL`). Commands ship as a fenced **copy-block in the
message content** (reliable one-tap copy); the embed carries the visual fields
WP-1 surfaced. Digest mode collapses a multi-candidate pass into one message.

No bot, no token, no tunnel, no Vera change. **Real one-tap buttons are
deferred** to future Vera/Discord work: webhooks can SEND embeds but cannot
RECEIVE component interactions, and the Vera/Hermes gateway cannot receive them
either (WP-0 discovery). The copy-block + CLI gate is the v1 affordance.

## Changes

- `packages/polymarket/notifications/discord.py`
  - `post_message(text="", *, embeds=None, webhook_url=None)`: now sends content
    and/or embeds in one webhook call. A content-only call still posts exactly
    `{"content": text}` (back-compatible — the typed risk/kill-switch/status
    helpers are unchanged and out of scope). Empty payload → returns False (no
    HTTP call). Never-raise contract preserved.
- `packages/polymarket/discovery/pending_notify.py`
  - `Poster` type is now `(content, embeds) -> bool`; `_default_post` wraps
    `post_message(content, embeds=embeds)`.
  - `_row_evidence(row)` extracted from `compute_row_evidence`: returns the
    structured `Evidence` (for embed fields) **and** the display string (for the
    digest field / fallback). `compute_row_evidence` is now a thin wrapper —
    `--list-pending` behaviour is byte-identical.
  - Pure builders: `build_pending_embed` (single card), `build_single_content`
    (heading + fenced copy-block), `build_digest_embed` (one stacked field per
    wallet), `build_digest_content` (per-wallet copy-blocks + overflow note),
    `_fit_digest` (greedy fit), `_humanize_source`, `_command_block`.
  - `notify_pending_candidate`: now posts the embed card (takes an `Evidence`).
  - `notify_pending_candidates`: filters invalid/already-notified, then 1 →
    single card, >1 → ONE digest message; marks notified only on a delivered
    send (all-or-nothing for the digest). Returns
    `{considered, posted, deduped, failed, mode[, skipped_capped]}`.
  - `format_pending_notification` retained as a LEGACY plain-text helper (still
    tested), no longer on the live path.

### Card design (as specified)

- Color bar = info/blue `0x3498DB` (review severity, NOT wallet quality).
- Title "Pending wallet review"; full address in the embed description.
- Fields: PnL, Win rate, Trades, CLV, **Positions** ("N open / M resolved"),
  **Discovery** (humanized: `loop_a`→"leaderboard discovery",
  `manual`→"manual", `loop_d`→"CLOB anomaly"). **Category** field only when
  present. Win rate renders `-` when there is no resolved book; category is
  omitted entirely when uncategorised. Footer "PolyTool - Vera" + timestamp.
- Commands in CONTENT as a fenced ```` ``` ```` block with full addresses (the
  CLI gate rejects truncated identifiers).

### Digest safety

`_fit_digest` greedily includes wallets up to `_DIGEST_MAX=10` AND a
`_CONTENT_BUDGET=1800` char budget, so a digest never exceeds Discord's 2000-char
content limit. Overflow is reported in-message ("+K more not shown; run
`discovery review --list-pending`") and via `skipped_capped` — never a silent
truncation. Only shown wallets are marked notified, so the overflow re-notifies
next pass.

## Verify (live, posted to the operator channel)

Posted with the REAL default metrics reader (on-disk scan data) and throwaway
temp dedup files (production `approvals_notified.json` untouched). Both messages
returned `delivered=True`.

**Single card** — `0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5`:
- embed: PnL `+$124.0k`, Win rate `62%`, Trades `50`, CLV `94%`, Positions
  `10 open / 40 resolved`, Discovery `leaderboard discovery`; color `3447003`
  (=0x3498DB), footer `PolyTool - Vera` + ISO timestamp; full address in
  description. Category omitted (wallet uncategorised). `mode=single`.
- content: fenced code block with the full-address approve/deny commands.

**Digest** — both pending wallets, ONE message, `mode=digest`, posted=2:
- embed `2 pending wallet reviews` with one field per wallet:
  - `0x84cf…` → `+$0 PnL, 50 trades, 50 open / 0 resolved, CLV 42%, via loop_a`
    (honestly explains the $0 PnL / absent win rate)
  - `0xcf60…` → `+$124.0k PnL, 62% win / 50 trades, 10 open / 40 resolved, CLV 94%, via loop_a`
- content: a fenced copy-block per wallet.

The commands are fenced code blocks, which is the mechanism Discord renders with
a one-tap copy button (operator confirms the tap in-client).

## Tests

- `tests/test_discord_notifications.py`: +3 — content+embeds together, embeds-only
  (no empty `content` key), nothing-to-send → False + no HTTP call. Existing
  exact-payload assertion (`{"content": ...}`) still passes.
- `tests/test_wallet_ingestion_notify.py`: reworked Part B to the new poster
  contract + new classes: `TestPendingEmbedCard` (shape/color/footer/address,
  win-rate dash, category omit/present, humanized sources), `TestCopyBlockContent`
  (fenced full-address commands, ASCII), `TestNotifySingle`, `TestNotifyDigest`
  (single vs digest threshold, one-message digest, mark-all-on-success, dedup
  second pass), `TestDigestFitAndOverflow` (cap, ≤2000-char content, overflow
  marks only shown), `TestNotifyNeverRaises` (single + digest poster raising →
  swallowed, nothing marked).
- Targeted: 186 passed (notify + discord + scan + wi5).
- Full suite: **5477 passed, 1 skipped, 3 failed**. The 3 failures are the
  pre-existing `tests/test_ris_phase4_source_acquisition.py` academic Marker-gate
  tests (confirmed pre-existing in WP-1 via `git stash`) — unrelated.
- CLI loads.

## Codex review

Skipped per policy: no mandatory-review paths touched (notification transport +
discovery notify builder; no `execution/`, kill-switch, risk, rate-limiter,
order placement / signing).

## Guards

Denylist untouched; secrets via `.env` (`DISCORD_WEBHOOK_URL`); never raises; no
bot / token / Vera changes; sender stays the webhook; one packet. The live-verify
helper was run from `artifacts/debug/` and removed afterward (avoids accidental
re-posting; gitignored regardless).

## Deferred

Real one-tap approve/deny buttons require an app/bot that can receive
`INTERACTION_CREATE`; the webhook cannot, and Hermes/Vera cannot today. Deferred
to future Vera/Discord work.
