# SPEC-0019: price_2min ClickHouse Acquisition Path v0

**Status**: Shipped (2026-03-16)
**Branch**: phase-1
**Supersedes**: None
**Related**: SPEC-0018, ARCHITECTURE.md (v4.2 Database Rule), CURRENT_STATE.md

---

## 1. Purpose

Implement the CLI-first acquisition path for 2-minute Polymarket price history
from the CLOB API into the canonical ClickHouse live series `polytool.price_2min`.

This is distinct from the SPEC-0018 bulk import path:

| | SPEC-0018 (`price_history_2min`) | SPEC-0019 (`price_2min`) |
|---|---|---|
| Table | `polytool.price_history_2min` | `polytool.price_2min` |
| Source | Local JSONL/CSV files | CLOB API (live fetch) |
| CLI | `import-historical --source-kind price_history_2min` | `fetch-price-2min` |
| Status | Legacy/optional under v4.2 | Canonical live series (v4.2) |
| Use case | One-time historical bulk download | Live-updating series for Silver reconstruction |

---

## 2. Architecture (v4.2 Database Rule)

ClickHouse handles all live streaming writes. `price_2min` is the live-updating
series written by this module. DuckDB handles all historical Parquet reads
(pmxt, Jon-Becker). These two planes never communicate.

---

## 3. Naming Resolution

Two names existed in the codebase/docs before this spec:

- `price_history_2min` — SPEC-0018 source kind, existing table `23_price_history_2min.sql`
- `price_2min` — ARCHITECTURE.md (live series column), roadmap authority doc

**Resolution**: these are two distinct use cases for the same API, not a rename
situation. Both names are correct for their respective paths. This spec ships
the `price_2min` path; `price_history_2min` is preserved as-is (off critical
path, optional legacy tooling).

---

## 4. ClickHouse Table Contract

**Table**: `polytool.price_2min`
**Schema file**: `infra/clickhouse/initdb/24_price_2min.sql`
**Engine**: `ReplacingMergeTree(imported_at)`
**ORDER BY**: `(token_id, ts)`
**Idempotency**: ReplacingMergeTree deduplicates on `(token_id, ts)` by
keeping the row with the latest `imported_at`. Re-running `fetch-price-2min`
for the same token is safe — rows are upserted, not duplicated.

| Column | Type | Notes |
|--------|------|-------|
| `token_id` | String | Polymarket CLOB token ID |
| `ts` | DateTime64(3, 'UTC') | 2-minute bucket timestamp from API |
| `price` | Float64 | Mid-price at the 2-minute bucket |
| `source` | LowCardinality(String) | Always `'clob_api'` for this path |
| `import_run_id` | String | UUID for the fetch run (provenance) |
| `imported_at` | DateTime64(3, 'UTC') | Server-side insert time (dedup key) |

Grafana read access: `GRANT SELECT ON polytool.price_2min TO grafana_ro;`

---

## 5. Fetch Layer

**Source**: Polymarket CLOB API
**Endpoint**: `GET https://clob.polymarket.com/prices-history?market=<token_id>&interval=max&fidelity=2`
**Authentication**: None required (public endpoint)
**Response shape**: `{"history": [{"t": <epoch_seconds>, "p": <price>}, ...]}`

The existing `ClobClient.get_prices_history()` from
`packages/polymarket/clob.py` is reused. No new HTTP dependencies added.

---

## 6. Module: `packages/polymarket/price_2min_fetcher.py`

Key exports:
- `normalize_rows(token_id, raw_history, run_id)` → `List[list]`
  Converts API records to CH-ready rows. Invalid/null timestamps are silently skipped.
- `FetchAndIngestEngine(config, *, _fetch_fn, _ch_client)`
  Injectable dependencies for offline testing. Real path uses `ClobClient` + `ClickHouseClient`.
- `FetchConfig` dataclass — connection settings for CLOB + ClickHouse
- `FetchResult` / `TokenFetchResult` dataclasses — run outcome and per-token stats

---

## 7. CLI: `fetch-price-2min`

```
python -m polytool fetch-price-2min --token-id <TOKEN_ID> [--token-id <ID2>...]
python -m polytool fetch-price-2min --token-file tokens.txt [--dry-run] [--out run_record.json]
```

**Key flags**:
- `--token-id ID` — Repeatable. Fetch one token per invocation.
- `--token-file PATH` — One token ID per line; `#` comments and blanks ignored.
- `--dry-run` — Normalize and count rows, but do not write to ClickHouse.
- `--out PATH` — Write `FetchResult.to_dict()` JSON to this path.
- `--clob-url URL` — Override default `https://clob.polymarket.com`.
- `--clickhouse-host/port/user/password` — CH connection. Password falls back
  to `CLICKHOUSE_PASSWORD` env var, then defaults to `polytool_admin`.

**Exit codes**: `0` on success; `1` if any token fetch/insert fails.

**Deduplication**: repeated token IDs in `--token-id` are deduplicated
preserving order before fetch.

---

## 8. Tests

File: `tests/test_fetch_price_2min.py`
Count: 30 tests, fully offline. No HTTP, no ClickHouse.

Test classes:
- `TestNormalizeRows` — row shape, timestamp conversion, skip logic (9 tests)
- `TestEngineWithDryRun` — dry-run mode, no CH writes (6 tests)
- `TestEngineWithLive` — live mode, CH insert payload, error handling (7 tests)
- `TestFetchPrice2MinCLI` — CLI behavior, token file, artifact output (8 tests)

---

## 9. Out of Scope

- Silver tape reconstruction (uses `price_2min` data; separate future spec)
- DuckDB integration for historical Parquet reads (separate)
- Scheduled / continuous refresh (n8n wrapper; future)
- FastAPI endpoint for `fetch-price-2min` (future)
- `price_history_2min` legacy path changes (none made)
