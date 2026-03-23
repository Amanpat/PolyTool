# price_2min ClickHouse Acquisition Path v0

**Date**: 2026-03-16
**Branch**: phase-1
**Spec**: SPEC-0019

---

## Summary

Implements the missing leg of the Phase 1 "FIRST: Bulk data import" item:
a CLI-first `fetch-price-2min` command that fetches 2-minute price history
from the Polymarket CLOB API and inserts it into a new canonical ClickHouse
table `polytool.price_2min`.

Resolves the `price_2min` vs `price_history_2min` naming conflict documented
in `2026-03-16_v42_docs_reconciliation.md`.

---

## Naming Decision: `price_2min` vs `price_history_2min`

Two names existed in the codebase before this packet:

| Name | Where | What it meant |
|------|-------|---------------|
| `price_history_2min` | `23_price_history_2min.sql`, SPEC-0018, `import-historical --source-kind` | Bulk import from local JSONL/CSV files |
| `price_2min` | `ARCHITECTURE.md`, roadmap authority doc | Live-updating ClickHouse series |

**Decision**: these are two distinct paths — not a rename. Both are retained:

- `price_history_2min` (table 23): unchanged. Legacy bulk-import from local files.
  Status: optional/off critical path under v4.2. No code or schema changed.
- `price_2min` (table 24, new): canonical live-updating series written by the
  new `fetch-price-2min` CLI. This is what Silver reconstruction will consume.

**Why not rename `price_history_2min` to `price_2min`?**
The existing table and importer are used by already-completed import artifacts
(`artifacts/imports/`, `import-historical` CLI). Renaming would break those
artifacts and the CLI's `--source-kind price_history_2min` flag. The two-table
approach has zero backwards-compatibility risk and clearly separates concerns.

**Backward compatibility**: `23_price_history_2min.sql` gets a naming note
comment at the top. `manifest.py` `_DESTINATION_TABLES` left unchanged (still
routes `price_history_2min` source kind to `polytool.price_history_2min`).

---

## Files Changed

| File | Change |
|------|--------|
| `infra/clickhouse/initdb/24_price_2min.sql` | New: canonical `price_2min` table, ReplacingMergeTree, Grafana read grant |
| `infra/clickhouse/initdb/23_price_history_2min.sql` | Added naming note comment at top (no schema change) |
| `packages/polymarket/price_2min_fetcher.py` | New: `FetchAndIngestEngine`, `normalize_rows`, `FetchConfig`, `FetchResult` |
| `tools/cli/fetch_price_2min.py` | New: `fetch-price-2min` CLI entry (`main(argv) -> int`) |
| `polytool/__main__.py` | Added `fetch_price_2min_main` entrypoint + help text + command registration |
| `tests/test_fetch_price_2min.py` | New: 30 offline tests |
| `docs/specs/SPEC-0019-price-2min-clickhouse-v0.md` | New: spec for this feature |
| `docs/dev_logs/2026-03-16_price_2min_clickhouse_v0.md` | This file |

---

## Design Decisions

**Reuse `ClobClient`**: `packages/polymarket/clob.py` already has
`get_prices_history(token_id, interval="max", fidelity=2)`. No new HTTP
library or `polymarket-apis` PyPI dependency added. The existing `HttpClient`
handles retries and backoff.

**Reuse `ClickHouseClient`**: The injectable `ClickHouseClient` from
`packages/polymarket/historical_import/importer.py` is reused via the
`CHInsertClient` protocol. No new CH dependency.

**`FetchAndIngestEngine` with injectable deps**: Both the fetch function
and CH client can be injected, enabling fully offline tests with zero mocking
of module internals.

**ReplacingMergeTree keyed on `(token_id, ts)`**: Idempotent — running
`fetch-price-2min` multiple times for the same tokens is safe. ClickHouse
keeps the latest row by `imported_at` (the dedup version column).

**`--dry-run` flag**: Normalizes rows and prints counts without writing to CH.
Useful for validation and offline CI.

---

## Commands Run

```bash
# Run new tests
python -m pytest tests/test_fetch_price_2min.py -v --tb=short
# => 30 passed in 0.26s

# Verify existing historical import tests unbroken
python -m pytest tests/test_historical_import_cli.py tests/test_historical_import_importer.py tests/test_historical_import_manifest.py -v --tb=short
# => 103 passed in 0.83s

# Smoke: CLI help works
python -m polytool fetch-price-2min --help
```

---

## Test Results

- 30 new tests: all passing, fully offline
- 103 existing historical import tests: all still passing
- No live network call attempted (Docker/ClickHouse not required for tests)

---

## Optional Live Smoke

Not attempted in this packet. To run manually when ClickHouse is up:

```bash
# Dry-run (no ClickHouse required)
python -m polytool fetch-price-2min \
    --token-id <SOME_TOKEN_ID> \
    --dry-run \
    --out artifacts/imports/price_2min_dry_run.json

# Live insert (requires ClickHouse running, table 24 must be created)
docker compose up -d
python -m polytool fetch-price-2min \
    --token-id <SOME_TOKEN_ID> \
    --out artifacts/imports/price_2min_run.json
```

Note: `24_price_2min.sql` is an initdb script. For existing Docker volumes,
run it manually:
```bash
docker compose exec clickhouse clickhouse-client \
    --user polytool_admin --password <pw> \
    --query "$(cat infra/clickhouse/initdb/24_price_2min.sql)"
```

---

## Open Questions for Silver Reconstruction Packet

1. **Token ID source**: Silver reconstruction needs to know which token IDs
   to pre-fetch. The DuckDB pmxt/Jon-Becker reads will expose which token IDs
   exist in the historical data. The `fetch-price-2min` CLI should be run with
   those IDs before Silver reconstruction starts.

2. **Full coverage vs on-demand**: Should `fetch-price-2min` pre-populate all
   tokens up-front, or should Silver reconstruction call it lazily per token?
   Lazy call avoids over-fetching; up-front populates the live CH table cleanly.

3. **`price_2min` vs `price_history_2min` for reconstruction**: Silver
   reconstruction should read from `polytool.price_2min` (the canonical live
   series from `fetch-price-2min`), NOT from `polytool.price_history_2min`
   (the legacy bulk-import table). This should be explicit in the Silver spec.

4. **Refresh cadence**: For Gate 2, a one-time fetch before the scenario sweep
   is sufficient. A periodic refresh cadence is a future n8n workflow concern.

5. **Token ID resolution**: Some pmxt/Jon-Becker records may use alias token
   IDs. Confirm whether `price_2min` should store canonical CLOB token IDs
   or alias IDs (or both). The CLOB API returns history by canonical ID.

---

## Notes on `price_history_2min` (legacy)

The legacy `price_history_2min` table and `import-historical --source-kind
price_history_2min` are unchanged. That path imports from local JSONL/CSV
files (e.g., files downloaded manually via the polymarket-apis PyPI package).
Under v4.2, it is off the critical path. It can still be used as an optional
cache if desired.

The canonical path for Silver reconstruction is `price_2min` via this module.
