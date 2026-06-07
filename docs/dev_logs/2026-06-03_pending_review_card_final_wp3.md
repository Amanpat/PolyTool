# 2026-06-03 — WP-3: Pending-review card final layout (handle headline, recent-form windows, CLV relabel, button confirm)

## Objective

Final layout for the wallet pending-review card, plus a confirm/lock on the Vera
button-disable behaviour. The card is built by the SHARED builder
`build_pending_embed` and serves BOTH surfaces — the webhook notification and the
Vera `/pending` bot card — so they improve together. Copy-block commands and the
gate action still use the FULL address (unchanged).

Scope: data layer (handle / last_active / recent-form windows / signal line / CLV
relabel) + embed redesign + bot button confirm. One packet, display/data only.

## Confirm-then-build findings (reported before building)

- **Handle (item 1):** NOT persisted on the watchlist row, NOT in the dossier
  header. The two real pending wallets (`0x84cf…`, `0xcf60…`) are wallet-address
  scans whose dossier header carries only `user_input` (the 0x address). The scan
  DOES call `/api/resolve`; `GammaClient.resolve()` populates `username` from a
  Gamma profile lookup when one exists, else `""` (most wallets are pseudonymous).
  → A real handle must be **captured at scan time** and persisted — a genuine new add.
- **last_active + recent-form (items 2–3):** Feasible. Dossier `positions[]` carry
  `entry_ts` / `exit_ts` (trade times), `close_ts` / `resolved_at` / `close_date_iso`
  (resolution date), `realized_pnl_net_estimated_fees`, and `resolution_outcome`.
  Header carries `max_trades` (sample cap) and `positions.count` (sample size) for
  the honesty rule. (An earlier read-only exploration claimed positions had no
  timestamps — that was wrong; verified against real artifacts.)
- **CLV (item 5):** `clv_coverage_rate` maps to `coverage.clv_coverage.coverage_rate`
  — a DATA-COMPLETENESS metric, not a closing-line-value edge signal. → relabelled
  **"CLV coverage"** everywhere on the card (embed field + digest/summary string).
- **Profile URL (item 7):** No canonical builder in repo; the address-keyed page
  `https://polymarket.com/profile/<address>` always resolves → used that.
- **Bot buttons (item 11):** `_finalize_done` already disables both buttons +
  relabels the title; `_disable_only` disables on the failure path;
  `_actioned_wallets` blocks re-clicks. The disable logic was **already correct and
  tested** (added in the Phase B commits) — the screenshot predated it. Confirmed +
  locked with an additional parity test; the handler itself was NOT modified.

### Operator-confirmed forks (AskUserQuestion)

1. **Handle path → "Dossier + reader"** (over literal "persist on the row"). The
   display path already RECOMPUTES evidence from scan data at display time (both
   surfaces go through `_row_evidence → _extract_user_metrics`), and last_active +
   windows MUST come from the dossier anyway. So all three new fields are sourced
   from the dossier via the shared reader — no watchlist-schema or worker change.
2. **"Today" window = UTC calendar day** (since 00:00 UTC); 7d / 30d are rolling.

## Changes

### Data layer

- `tools/cli/scan.py`
  - `_persist_dossier_header_username(output_dir, username)`: stamps
    `resolve_response.username` onto `dossier.json` `header.username` after the
    dossier is materialised (non-empty only; never overwrites; **non-fatal** — a
    stamp failure can never break the scan). Wired into `_emit_trust_artifacts`.
- `tools/cli/wallet_scan.py`
  - New pure helpers: `_parse_iso_ts`, `_iso_z`, `_dossier_positions`,
    `_newest_trade_ts` (newest entry/exit ts — a TRADE time, not the resolution),
    `_recent_form_from_positions` (resolved-trade `{close, pnl}` rows +
    `sample_size` + `sample_cap`).
  - `_extract_user_metrics(run_root)`: now also reads `dossier.json` (additive,
    defensive) and surfaces `handle` (header.username, `@`/whitespace-stripped),
    `last_active`, `win_count` (WIN+PROFIT_EXIT, None with no resolved book), and
    `recent_form`. Coverage/segment extraction unchanged.
- `packages/polymarket/discovery/evidence_summary.py`
  - `Evidence`: + `handle`, `win_count`, `last_active`, `recent_form` (all Optional;
    `recent_form` is a read-only dict). `from_dict` wires them.
  - `summarize_evidence`: `CLV X%` → **`CLV coverage X%`** (honest relabel). Field
    order otherwise unchanged.

### Embed redesign (shared builder)

- `packages/polymarket/discovery/pending_notify.py`
  - `_FOOTER_TEXT` → `"PolyTool · Vera"`; new `_ABSENT = "—"` honest-omission
    marker; `_PROFILE_URL`.
  - New display helpers: `_now_dt`, `_parse_iso`, `_short_addr`, `_profile_url`,
    `_relative_age` (Nd/Nh/<1h ago), `_signal_line` (discovery · win (n/d) · active
    Nd ago, honest omission), `_window_starts`, `_recent_form_values` (the honesty
    rule).
  - `build_pending_embed` rebuilt: author eyebrow "Pending wallet review"; TITLE =
    handle (→ truncated address → "Unnamed wallet"); description = truncated address
    (code) + "View on Polymarket" link (from full address) + signal line; two rows
    of three inline fields (PnL all-time/N resolved · Win rate `62% (25/40)` · Last
    active // Trades `(sampled)` · CLV coverage · Discovery); a full-width
    "Recent form — full trade history" separator + three inline windows Today / 7
    days / 30 days; blue bar (review); footer + timestamp. The Category field was
    dropped from the single card (focus remains in the digest summary line).

### Honesty rule (recent-form windows)

A window W is shown iff the sample fully covers it: **not truncated**
(`sample_size < sample_cap` — we hold all their trades) OR **oldest sampled
resolution older than the window start** (nothing inside the window was dropped).
Uncovered → `—` (never a partial number). Covered with no in-window trades → `+$0`
(honest). On the current 50-trade samples (cap 200), all windows are covered today;
they will keep populating once all-trades collection lands.

### Bot (confirm-only)

- `packages/polymarket/discord_bot/approvals.py` — **unchanged.** The redesigned
  embed flows into `/pending` via the read-only `_build_embed` →
  `discord.Embed.from_dict` (verified it accepts the author field + 10 fields, and
  `_finalize_done` preserves them while relabelling title/colour). Button disable +
  idempotency are unchanged and remain green.

## Tests

- `tests/test_wallet_scan.py`: + `TestExtractUserMetricsDossierFields` (handle
  strip / absent / no-dossier; last_active = newest trade ts; recent_form
  resolved-only + sample_size/cap; win_count).
- `tests/test_wallet_ingestion_notify.py`: reworked `TestPendingEmbedCard` to the
  new shape (handle headline, author eyebrow, truncated address + profile link,
  `CLV coverage`, win `(25/40)`, `(sampled)`, recent-form row, title fallback); new
  `TestRecentFormHonesty` (full-coverage / truncated-uncovered → `—` / covered-zero
  → `+$0` / no-data) and `TestSignalLineAndRecency`; CLV-label updates across
  evidence-string tests.
- `tests/test_vera_approvals.py`: + `test_build_embed_uses_shared_redesigned_card`
  (the bot card IS the shared redesigned builder — author eyebrow, `CLV coverage`,
  recent-form row, truncated-address title). Existing button-disable / idempotency
  tests unchanged and passing.

### Results

- Targeted: `test_wallet_ingestion_notify + test_wallet_scan + test_vera_approvals
  + test_discord_notifications` = **191 passed**; `test_wallet_discovery_two_tier`
  (CLV-label string fixed) green.
- Full suite: **5545 passed, 1 skipped, 4 failed**. The 4 are NOT this packet:
  3 × `test_ris_phase4_source_acquisition.py` (academic Marker-gate, pre-existing
  in WP-1/WP-2) and 1 × `test_ris_monitoring.py::...test_ingest_writes_run_log`
  (a cross-test ordering flake — passes on the clean tree AND with this packet's
  changes when run in isolation; unrelated RIS ingest run-log, nothing this packet
  touches). My only full-suite breakage was the two-tier CLV-label assertion, now
  fixed.
- CLI loads (`python -m polytool --help`); all touched modules import clean.

## Live verification (operator)

The bot needs a token + tunnel (operator infra), so the live steps are operator-run:

1. Re-scan a NAMED wallet (Gamma profile exists) and a pseudonymous one →
   `discovery review --list-pending` / webhook: confirm handle headline vs address
   fallback, signal line, recency, `CLV coverage`, recent-form row (covered windows
   populate; uncovered show `—`).
2. `/pending` in Discord → action a real wallet → buttons disable, title shows the
   outcome, second click is a no-op (gate idempotency is the backstop).
3. Confirm the content copy-block + gate action still carry the FULL address.

> Note: existing on-disk dossiers predate the username stamp, so `handle` renders as
> the address fallback until wallets are re-scanned — honest by design.

## Guards

Shared builder serves both surfaces; copy-block + gate use the full address;
denylist untouched; secrets via `.env` (never logged); honest omission throughout
(`—`, never a fabricated 0); one packet; tree left for review.

## Codex review

The mandatory Codex trigger is the write-surface handler (`approvals.py`) — which
this packet did NOT modify (button disable was already correct; confirmed + locked
with a test). So no handler-change adversarial review is required by the file-path
policy. The substantive changes (embed builder, evidence, scan metrics) are
display/data = standard review. Codex adversarial review not run (no
write-surface change to review); available on request via
`/codex:review --background` over the diff.
