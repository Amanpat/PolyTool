# Dev Log: Wallet-Scan v0 (2026-03-05)

## Summary

Implemented `polytool wallet-scan` — a research-only batch scan workflow that
accepts a mixed list of Polymarket identifiers (handles and wallets), runs a
standardized scan for each, and emits a deterministic leaderboard artifact.

---

## Files Touched

| File | Change |
|---|---|
| `tools/cli/wallet_scan.py` | New — CLI entrypoint + WalletScanner class |
| `polytool/__main__.py` | Added `wallet-scan` command routing |
| `tests/test_wallet_scan.py` | New — unit tests (no network, no ClickHouse) |
| `docs/specs/SPEC-wallet-scan-v0.md` | New — spec |
| `docs/dev_logs/2026-03-05_wallet_scan_v0.md` | This file |

---

## Design Choices

### Injection pattern (mirrors batch_run.py)

`WalletScanner` accepts an optional `scan_callable` injected at construction
time. The default uses the real `scan.run_scan()` path. Tests inject a fake
callable that returns a pre-built run_root directory. This keeps tests fully
offline (no ClickHouse, no API).

### Identity resolution at two layers

1. **Pre-scan**: `resolve_user_context` derives the slug for failure records
   and path routing before the scan runs.
2. **Scan itself**: the raw identifier is passed to the scan callable, which
   handles `--user @handle` vs `--wallet 0x...` internally.

### Input type detection

- Lines starting with `@` → handle
- Lines starting with `0x` (case-insensitive) → wallet
- Everything else → handle (best-effort)

This matches how users naturally write identifiers and requires no extra
metadata in the file.

### Metrics extraction

Metrics are pulled from `coverage_reconciliation_report.json` in the scan
run_root. The primary sort metric is `realized_pnl_net_estimated_fees_total`
from the `pnl` section — the net PnL after estimated fees, which is the most
conservative and comparable figure across users.

CLV coverage rate, outcome counts, and segment highlights are surfaced as
supplementary fields.

### Leaderboard ordering

1. `realized_net_pnl` descending (higher is better)
2. Tiebreak: `slug` ascending (deterministic alphabetical)
3. Null PnL (scan with no PnL data) → treated as float('inf') in sort key,
   placing them after all valid PnL entries

### Error isolation

Each entry is wrapped in `try/except`. On failure, `status="failure"` and the
exception type+message are recorded in `error`. The batch continues to the next
entry. Only succeeded entries appear in `ranked`; all entries (including
failures) appear in `per_user_results.jsonl`.

### Artifact layout

```
artifacts/research/wallet_scan/<YYYY-MM-DD>/<run_id>/
  wallet_scan_manifest.json
  per_user_results.jsonl
  leaderboard.json
  leaderboard.md
```

Same `<date>/<run_id>` structure as `batch_run`. Safe to rerun: each run gets
a fresh UUID directory.

---

## Tests

`tests/test_wallet_scan.py` covers:

- `parse_input_file`: handles, wallets, blank/comment skipping, deduplication,
  `max_entries` cap, missing file, case-insensitive 0X prefix
- `_detect_identifier_type`: all three paths
- `WalletScanner` artifacts: all four files written, correct path structure,
  manifest contents, JSONL format
- Partial failure: one-fails-rest-continues, error field recorded, leaderboard
  excludes failures
- Leaderboard ordering: descending by PnL, tiebreak by slug, null PnL last,
  1-based rank
- Markdown: run_id present, table rows for ranked entries

All tests use injected fake scan callables — no network, no ClickHouse.

---

## Not Implemented (v0 scope)

- Parallel scan workers (sequential only)
- LLM calls or report generation
- Top performer discovery from external sources
- Run-to-run diff
- `--aggregate-only` mode (re-aggregate without re-scanning)
