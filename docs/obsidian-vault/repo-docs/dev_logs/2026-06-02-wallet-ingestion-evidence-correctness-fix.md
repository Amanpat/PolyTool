---
title: Wallet Ingestion Evidence Correctness Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_wallet-ingestion-evidence-correctness-fix.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-06-02 — Wallet-ingestion evidence-correctness fix

**Follow-up to** `2026-06-01_wallet-ingestion-notify-and-evidence.md`. Live
verification showed the computed-evidence branch firing but emitting
internally-inconsistent values:

- `0x84cf…`: `+$0 PnL, 0 trades, CLV 42%`
- `0xcf60…`: `+$124.0k PnL, 0 trades, CLV 94%`

`+$124k PnL` with `0 trades` is impossible from the same data — a mis-sourced /
defaulting field, the same field-name-mismatch class as the known MVF/scan
degradations and the dropped maker/taker attribution.

## Root cause (traced)

`tools/cli/wallet_scan.py::_extract_user_metrics` is the source `compute_row_evidence`
→ `summarize_evidence` reads from. It mis-sourced fields against the REAL
persisted schema produced by `polytool/reports/coverage.py::build_coverage_report`:

| field | reader read | actually persisted at | result |
|---|---|---|---|
| trade count | `coverage["positions_total"]` (top level) | `coverage["totals"]["positions_total"]` | `int(None or 0)` → **always 0** |
| unknown-res % | `coverage["outcome_pcts"]` | `coverage["outcome_percentages"]` | always None |
| win rate | *(never extracted)* | derivable from `coverage["outcome_counts"]` | always omitted |

PnL and CLV read correctly because `pnl` and `clv_coverage` *are* top-level keys —
hence the partial, inconsistent output.

**Why it shipped:** the unit fixture `tests/test_wallet_scan.py::_make_coverage_report`
encoded the WRONG schema (top-level `positions_total`, `outcome_pcts`), matching
the buggy reader and masking the defect.

## Fix

**`_extract_user_metrics` (the source of truth):**
- `positions_total` now read from `coverage["totals"]["positions_total"]`, with a
  legacy top-level fallback. CRITICAL: genuinely-absent → `None` (new helper
  `_coerce_int_or_none`), **not 0**, so the summary omits "trades" instead of a
  misleading "0 trades".
- `win_rate` now computed from `outcome_counts` via `_win_rate_from_outcome_counts`,
  mirroring the canonical `_finalize_segment_bucket` formula:
  `(WIN+PROFIT_EXIT)/(WIN+LOSS+PROFIT_EXIT+LOSS_EXIT)`; `None` (omit, never 0%)
  when the book has no resolved outcomes.
- `unknown_resolution_pct` reads `outcome_percentages` (legacy `outcome_pcts`
  fallback).
- `None` positions are already handled by all downstream consumers (leaderboard
  md `… or 'null'`, `_failure_result` already used `None`).

**Display-layer guard** in `packages/polymarket/discovery/pending_notify.py`
(`_drop_inconsistent_zero`, applied inside `compute_row_evidence`): if a trade
count is 0/missing while realized PnL or CLV indicates real activity, the count
is marked UNAVAILABLE (omitted) rather than shown as "0 trades". Defense-in-depth
against future source regressions; never fabricates a count.

`summarize_evidence`'s deterministic WI-5 contract is left untouched (the guard
lives in the display path, not the shared pure summarizer).

## Full-set sanity check (point 3)

Audited every field `summarize_evidence` emits — PnL ✓ (was correct), win/trades
✗→fixed, CLV ✓ (was correct), churn (row-sourced, n/a). Also fixed the
non-emitted `unknown_resolution_pct` key while in the same function.

## Tests

`tests/test_wallet_scan.py` — fixture corrected to the real schema (`totals.*`,
`outcome_percentages`); new `TestExtractUserMetrics` (nested read, win-rate
extraction, PnL/CLV still correct, **non-zero PnL ⇒ non-zero trades**, missing →
`None` not 0, legacy fallback) and `TestWinRateFromOutcomeCounts`.

`tests/test_wallet_ingestion_notify.py` — new `TestEvidenceInternalConsistency`:
full metrics render consistently (`+$124.0k PnL, 64% win / 180 trades, CLV 94%`);
a regressed `positions_total=0` beside non-zero PnL never renders "0 trades";
missing-trades-with-CLV omits trades; genuine no-activity left alone.

### Results

```
tests/test_wallet_scan.py + test_wallet_ingestion_notify.py + two_tier + scan_worker + wi5  → 168 passed
full suite (minus pre-existing native-crash fetcher classes) → 5403 passed, 1 skipped
```

Pre-existing, unrelated (RIS academic pipeline, not this change):
`test_ris_fetchers.py::TestLiveAcademicFetcher` SIGSEGV (feedparser native) and 3
`test_ris_phase4_source_acquisition` Marker-gate failures — identical to the prior
session's baseline; my change adds 13 tests and introduces no new failures.

## Guards

Denylist untouched (no execution/kill-switch/risk/EIP-712/order paths). No secrets
handling. One packet. Codex review tier = skip (scan-metrics extraction + display
path only). Stop for Codex re-verification.
