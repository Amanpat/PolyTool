---
title: Pending Review Fields Wp1
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_pending_review_fields_wp1.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-06-02 — WP-1: Surface + verify new pending-review fields (data layer)

## Objective

Add three fields to the wallet pending-review evidence summary, ahead of the
approval-bot packet (WP-2). Data layer only — no bot, no notification-sender
change. Every displayed field verified accurate on the two REAL pending wallets
(the "0 trades" lesson: a field must reflect real scan data, not a wrong-fixture
assumption).

Fields added, in the packet's cost order:

1. **Open-vs-resolved split** (free — already in the metrics dict via
   `outcome_counts`): `resolved = WIN+LOSS+PROFIT_EXIT+LOSS_EXIT`, `open = PENDING`.
2. **Discovery source/signal** (from the watchlist ROW, not metrics): `row.source`
   (`loop_a`/`manual`/`loop_d`), rendered `via <source>`.
3. **Category focus** (scoped extractor change): dominant *known* category.

Explicitly NOT added (confirmed unavailable, no fabrication): account age /
first-seen (no such field), total capital deployed (only PnL exists).

## Key deviation (surfaced, not improvised)

The packet said to surface `category_coverage` and "pick the dominant category."
On inspection, `category_coverage` (coverage report) holds only
`present_count / missing_count / coverage_rate / source_counts` — a data-quality
rate, **no per-category breakdown**. A dominant category can only come from
`segment_analysis.by_category`, which has per-category `count` buckets (built by
`polytool/reports/coverage.py`). Surfacing `coverage_rate` as "category focus"
would itself be the misleading-field bug the packet warns against. Implemented
against `by_category` (the faithful source for the stated goal). `_extract_user_metrics`
already loads the segment file for `by_entry_price_tier`, so this was a scoped
addition, not a new read.

## Changes

- `packages/polymarket/discovery/evidence_summary.py`
  - `Evidence`: + `open_positions`, `resolved_positions`, `category_focus`, `source` (all Optional).
  - `Evidence.from_dict`: derives open/resolved from `outcome_counts` (PENDING vs
    the four resolved buckets; UNKNOWN_RESOLUTION excluded from both); reads
    `category_focus` and `source`; explicit `open_positions`/`resolved_positions`
    keys take precedence over the derivation.
  - `summarize_evidence`: appends segments in a fixed order — PnL, win/trades,
    **open/resolved**, CLV, churn, **focus**, **via source**. All conditional, so
    absent fields are omitted (backward compatible).
  - New helpers: `_clean_str`, `_open_resolved_from_outcome_counts`.
- `tools/cli/wallet_scan.py`
  - New `_dominant_category(by_category)`: highest-`count` known category;
    excludes the synthetic "Unknown" bucket (case-insensitive); ties broken
    alphabetically; returns None when entirely uncategorised. Never raises.
  - `_extract_user_metrics`: adds `"category_focus"` to the returned dict.
- `packages/polymarket/discovery/pending_notify.py`
  - `compute_row_evidence`: injects `row["source"]` into the metrics data before
    building `Evidence`. New `_has_substantive_evidence` guard so a row carrying
    only provenance (`source`) falls back to the stored reason rather than
    presenting "via loop_a" as if it were performance evidence.

No change to the notification sender (still the webhook via `post_message`);
no embed/button work; denylist untouched; no secrets.

## Accuracy gate

### Unit tests (real-schema fixtures)

- `tests/test_wallet_scan.py`: `TestDominantCategory` (6), `TestExtractUserMetricsCategoryFocus` (3).
  Fixtures mirror the real `segment_analysis.json` shape (top-level
  `segment_analysis` → `by_category` → `{count, ...}` buckets with a synthetic
  "Unknown"). Includes the all-Unknown case (= both real wallets → None).
- `tests/test_wallet_ingestion_notify.py`: `TestOpenResolvedSplit` (5),
  `TestSourceSignal` (3), `TestCategoryFocusRendering` (3). `outcome_counts`
  fixtures carry all six KNOWN_OUTCOMES keys and replicate the two live wallets'
  exact counts; one test asserts UNKNOWN_RESOLUTION is excluded from both sides.

### Live verify — `discovery review --list-pending` on the 2 real pending wallets

| Wallet | Rendered evidence | Checks against scan data |
|---|---|---|
| `0x84cfffc3f16dcc353094de30d4a45226eccd2f63` | `+$0 PnL, 50 trades, 50 open / 0 resolved, CLV 42%, via loop_a` | outcome_counts PENDING=50, rest 0 → 50 open / 0 resolved ✓. Honestly explains $0 PnL + absent win rate (no resolved book). Category all-Unknown → omitted ✓. source=loop_a ✓. |
| `0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5` | `+$124.0k PnL, 62% win / 50 trades, 10 open / 40 resolved, CLV 94%, via loop_a` | WIN22+LOSS13+PROFIT_EXIT3+LOSS_EXIT2=40 resolved, PENDING=10 open ✓. Win 62% = (22+3)/40 ✓. Category all-Unknown → omitted ✓. source=loop_a ✓. |

Real-data note: both live wallets are entirely uncategorised (`category_coverage.present_count=0`,
`by_category` = `{Unknown: 50}`), so category focus correctly renders nothing
today. The field is wired and tested; it will populate once categorised scans
exist. Also note `row.reason` is the generic worker string on both wallets
("scan-worker drained scan_queue..."), which is why evidence is recomputed at
display time and `source` (not the generic reason) is the meaningful signal;
`churn_triggered` is not a watchlist column and is not fabricated.

## Test results

- Targeted: `test_wallet_scan.py` + `test_wallet_ingestion_notify.py` = **85 passed**.
- Full suite: **5461 passed, 1 skipped, 3 failed**. The 3 failures are in
  `tests/test_ris_phase4_source_acquisition.py` (academic Marker-quality gate) and
  are **pre-existing on the clean tree** (verified via `git stash`) — unrelated to
  this packet (RIS academic ingest, not discovery evidence).
- CLI loads (`python -m polytool --help`).

## Codex review

Skipped per policy: no mandatory-review paths touched (no `execution/`,
`kill_switch.py`, `risk_manager.py`, `rate_limiter.py`, `pair_engine.py`,
`reference_feed.py`, order placement / signing). Changes are research/notification
data-layer (evidence summary + scan metrics extraction).

## Open questions / next (WP-2)

- Embed/button layout and the sender split (pending card → bot, alerts → webhook)
  belong to the approval-bot packet, not here.
- Category focus is dormant until categorised scans land; consider whether the
  scan path should backfill `category` for these wallets (separate packet).
