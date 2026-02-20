# Feature: CLV cache warm

## Summary
A new scan sub-step can warm CLV price snapshots before CLV computation:
- `--warm-clv-cache`

This pre-populates `market_price_snapshots` so later runs can compute CLV from cache, including in offline mode.

## Usage
Basic:
```bash
python -m tools.cli.scan --user "@<user>" --warm-clv-cache
```

Warm then compute:
```bash
python -m tools.cli.scan --user "@<user>" --warm-clv-cache --compute-clv
```

Optional env:
- `SCAN_WARM_CLV_CACHE=true`

## Behavior
- Scans dossier positions for CLV-eligible rows (`token_id` + resolvable `close_ts`).
- Performs bounded `/prices-history` requests per eligible position.
- Persists fetched points to `market_price_snapshots`.
- Emits summary artifact:
  - `clv_warm_cache_summary.json`
  - includes:
    - `attempted`
    - `cache_hit_count` (already cached; no fetch needed)
    - `fetched_count` (network request attempted)
    - `inserted_rows_count` (rows inserted this run)
    - `succeeded_positions_count` (snapshot available via cache hit or fetched points)
    - `failed_positions_count`
    - `failure_reason_counts`
    - `failure_samples` (up to 5 with `token_id`, `reason`, `error_detail`)
- Never blocks scan completion.

## Verification
1. Run warm-cache scan.
2. Confirm artifact exists:
   - `clv_warm_cache_summary.json`
3. Confirm manifest wiring:
   - `run_manifest.json` contains `output_paths.clv_warm_cache_summary_json`
4. Confirm DB impact (online success case):
   - snapshot row count in `market_price_snapshots` increases.
5. Confirm failure diagnostics (failure case):
   - `failure_reason_counts` includes actionable reason codes (`CONNECTIVITY`, `RATE_LIMITED`, etc.).
   - `failure_reason_counts` never uses `UNSPECIFIED`.
   - `failure_samples` includes reason + detail snippet for quick triage.
