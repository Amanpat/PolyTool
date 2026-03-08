# Feature: Wallet-Scan v0

**Status**: Implemented (2026-03-05)
**Spec**: [docs/specs/SPEC-wallet-scan-v0.md](../specs/SPEC-wallet-scan-v0.md)
**CLI command**: `python -m polytool wallet-scan`

---

## What it does

`wallet-scan` accepts a plain-text file of Polymarket identifiers (wallet addresses
and/or handles, one per line), runs a standardized research scan for each, and
produces a **deterministic leaderboard** artifact ranked by net PnL after estimated fees.

This is a **research-only** workflow. No orders are placed. No external LLM API
calls are made. All outputs land in `artifacts/research/wallet_scan/`.

---

## CLI usage

```bash
python -m polytool wallet-scan \
  --input wallets.txt \
  [--profile lite|full] \
  [--out artifacts/research/wallet_scan] \
  [--max-entries N]
```

### Input file format

One identifier per line:

```
# Sports traders
@DrPufferfish
@Alice
0xdeadbeef1234567890abcdef1234567890abcdef
# blank lines and # comments are ignored
```

- Lines starting with `@` → Polymarket handle
- Lines starting with `0x` (case-insensitive) → wallet address
- `#` and blank lines → skipped
- Duplicate lines → deduplicated (first occurrence wins)

### Scan profiles

| Profile | Stages enabled |
|---------|---------------|
| `lite` (default) | positions + PnL + resolution enrichment + CLV |
| `full` | all scan stages |

---

## Output files

```
artifacts/research/wallet_scan/
  <YYYY-MM-DD>/
    <run_id>/
      wallet_scan_manifest.json   -- run metadata + per-entry output_paths
      per_user_results.jsonl      -- one JSON object per identifier (all statuses)
      leaderboard.json            -- deterministic ranked list (succeeded only)
      leaderboard.md              -- human-readable top-20 table
```

Each run creates a fresh `<date>/<run_id>/` directory. Reruns never overwrite
prior results.

### Key fields in `per_user_results.jsonl`

| Field | Description |
|-------|-------------|
| `identifier` | Original input (`@Alice` or `0x...`) |
| `slug` | Resolved canonical slug |
| `status` | `"success"` or `"failure"` |
| `realized_net_pnl` | Net PnL after estimated fees (primary sort key) |
| `gross_pnl` | PnL before fees |
| `positions_total` | Total position count |
| `clv_coverage_rate` | Fraction of positions with CLV data [0–1] |
| `unknown_resolution_pct` | Fraction with UNKNOWN_RESOLUTION outcome [0–1] |
| `error` | Exception message on failure; null on success |

### Leaderboard ordering

1. `realized_net_pnl` descending
2. Tiebreak: `slug` ascending (alphabetical, deterministic)
3. Entries with `status="failure"` are excluded from `ranked`

---

## Failure handling + determinism

- One failed entry does **not** abort the batch (`--continue-on-error` default: true)
- Failed entries record `status="failure"` + `error` in `per_user_results.jsonl`
- Leaderboard is deterministic for the same input + same scan data
- Metrics come from `coverage_reconciliation_report.json` in each scan run_root

---

## Limitations (v0)

- Sequential execution only (no parallel scan workers)
- No LLM calls or report generation
- No diff between wallet-scan runs
- Segment highlights are informational only (not ranked)

---

## Next step: alpha-distill

Feed the output of `wallet-scan` into `alpha-distill` to aggregate cross-user
segment metrics and generate ranked edge hypothesis candidates:

```bash
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/2026-03-05/<run_id>
```

See [docs/features/alpha-distill-v0.md](alpha-distill-v0.md).
