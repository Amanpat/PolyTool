# SPEC-wallet-scan-v0: Batch Wallet Scan with Deterministic Leaderboard

## Status

Draft — implemented in `tools/cli/wallet_scan.py` (2026-03-05).

---

## Purpose

`wallet-scan` is a research-only CLI workflow that accepts a mixed list of
Polymarket identifiers (handles and wallet addresses), runs a standardized scan
for each, and produces a deterministic leaderboard artifact. No trading, no
order placement, no external LLM API calls.

---

## CLI Interface

```
python -m polytool wallet-scan \
  --input wallets.txt \
  [--profile lite|full] \
  [--out artifacts/research/wallet_scan] \
  [--run-id <uuid>] \
  [--max-entries N] \
  [--no-continue-on-error]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--input` | (required) | Path to input file with one identifier per line |
| `--profile` | `lite` | Scan profile: `lite` (positions+pnl+clv) or `full` |
| `--out` | `artifacts/research/wallet_scan` | Output root directory |
| `--run-id` | random uuid4 | Unique run ID for this batch |
| `--max-entries` | (none) | Safety cap on identifiers loaded |
| `--continue-on-error` | true | Continue on per-entry failures |

---

## Input Format

One identifier per line. Type is detected automatically:

- Lines starting with `@` → **handle** (e.g., `@DrPufferfish`)
- Lines starting with `0x` (case-insensitive) → **wallet address**
- Lines starting with `#` or blank → ignored (comments / whitespace)
- Duplicate lines are deduplicated (first occurrence wins)

Example:
```
# Sports traders
@DrPufferfish
@Alice
0xdeadbeef1234567890abcdef1234567890abcdef
# Another wallet
0xCAFEBABE...
```

---

## Scan Profiles

| Profile | Flags |
|---|---|
| `lite` | `--lite --ingest-positions --compute-pnl --enrich-resolutions --compute-clv` |
| `full` | `--full --ingest-positions --compute-pnl --enrich-resolutions --compute-clv` |

The `lite` profile is the default. It activates the subset of scan stages
relevant for quick multi-user research: position ingestion, PnL computation,
resolution enrichment, and CLV capture.

---

## Output Structure

```
artifacts/research/wallet_scan/
  <YYYY-MM-DD>/
    <run_id>/
      wallet_scan_manifest.json   -- run metadata + output_paths
      per_user_results.jsonl      -- one JSON object per identifier (all statuses)
      leaderboard.json            -- sorted deterministic leaderboard
      leaderboard.md              -- human-readable top-20 table
```

Each run creates a new unique directory (`<date>/<run_id>/`). Reruns are safe;
they never overwrite each other.

---

## per_user_results.jsonl Schema

Each line is a valid JSON object with the following fields:

| Field | Type | Notes |
|---|---|---|
| `identifier` | string | Original input line (e.g., `@Alice` or `0x...`) |
| `kind` | `"handle"` \| `"wallet"` | Detected type |
| `slug` | string \| null | Resolved slug (e.g., `alice`) |
| `run_root` | string \| null | Path to scan run artifacts; null on failure |
| `status` | `"success"` \| `"failure"` | Per-entry scan outcome |
| `error` | string \| null | Error message on failure; null on success |
| `realized_net_pnl` | float \| null | Net PnL after estimated fees (primary sort key) |
| `gross_pnl` | float \| null | Gross PnL before fees |
| `positions_total` | int \| null | Total position count |
| `clv_coverage_rate` | float \| null | CLV coverage rate [0–1] |
| `unknown_resolution_pct` | float \| null | UNKNOWN_RESOLUTION outcome rate [0–1] |
| `outcome_counts` | object | WIN/LOSS/etc counts |
| `segment_highlights` | string[] | Top segment summary lines (informational) |

---

## leaderboard.json Schema

```json
{
  "run_id": "<uuid>",
  "created_at": "<ISO-8601 UTC>",
  "profile": "lite",
  "scan_flags": { ... },
  "input_file": "wallets.txt",
  "entries_attempted": 5,
  "entries_succeeded": 4,
  "entries_failed": 1,
  "ranked": [
    {
      "rank": 1,
      "slug": "alice",
      "identifier": "@Alice",
      "realized_net_pnl": 12.345678,
      "gross_pnl": 13.0,
      "positions_total": 42,
      "clv_coverage_rate": 0.75,
      "unknown_resolution_pct": 0.02,
      "run_root": "artifacts/dossiers/users/alice/..."
    },
    ...
  ]
}
```

---

## Deterministic Ordering

Leaderboard entries are sorted:

1. **Primary**: `realized_net_pnl` descending (highest net PnL first)
2. **Secondary tiebreak**: `slug` ascending (alphabetical)
3. **Null handling**: entries with `realized_net_pnl = null` (failed scans are
   excluded from ranked; only succeeded entries appear in `ranked`)

Failures are excluded from `ranked` but are recorded in `per_user_results.jsonl`.

---

## Error Handling

- One bad wallet cannot kill the batch (`--continue-on-error` is default `true`)
- Each failed entry records `status="failure"` and an `error` field with the
  exception type and message
- The manifest records total `entries_attempted`, `entries_succeeded`, `entries_failed`

---

## Identity Resolution

Each identifier is resolved via `polytool.user_context.resolve_user_context`:
- `@handle` → `handle=identifier`
- `0x...` → `wallet=identifier`

Resolution is used for slug derivation (for path routing) only. The scan itself
receives the raw identifier and handles the full identity flow.

---

## Limitations (v0)

- Sequential scan execution (no parallelism)
- No automatic "top performer discovery" from external sources
- No LLM calls or report generation
- No diff between runs
- Segment highlights are informational only (not ranked)

---

## Files

| Path | Role |
|---|---|
| `tools/cli/wallet_scan.py` | CLI entrypoint + WalletScanner class |
| `polytool/__main__.py` | Command registration (`wallet-scan`) |
| `tests/test_wallet_scan.py` | Unit tests |
| `docs/specs/SPEC-wallet-scan-v0.md` | This spec |
