# PDR - Roadmap 5.1A CLV Operational Verification

Roadmap 5.1A CLV was executed in a real scan run and verified end-to-end through trust artifacts and ClickHouse. The pipeline produced deterministic null-plus-reason CLV outputs, but measured CLV coverage was 0.0% due missing close timestamps and live `/prices-history` failures, so this is a **no-go** for Roadmap 5.2 at this time.

---

## Run Context

- Date: 2026-02-19
- User: `@drpufferfish`
- Run root:
  - `artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-19/1bf1b3b1-55be-4745-8418-f68bd614056a`

---

## Commands Run

1. Apply CLV snapshots migration:
   - `Get-Content infra/clickhouse/initdb/20_clv_price_snapshots.sql -Raw | docker exec -i polyttool-clickhouse clickhouse-client -d polyttool --multiquery`
2. Verify migration table exists:
   - `docker exec -i polyttool-clickhouse clickhouse-client -d polyttool -q "SHOW TABLES LIKE 'market_price_snapshots'"`
   - `docker exec -i polyttool-clickhouse clickhouse-client -d polyttool -q "SHOW CREATE TABLE market_price_snapshots"`
3. Run CLV-enabled scan:
   - `python -m polytool scan --user "@drpufferfish" --compute-clv --enrich-resolutions`
4. Inspect artifacts:
   - `coverage_reconciliation_report.json`
   - `coverage_reconciliation_report.md`
   - `audit_coverage_report.md`
   - `dossier.json`
5. Query snapshot counts (global and run token set):
   - ClickHouse queries over `market_price_snapshots` (see devlog for exact script and output).

---

## CLV Coverage Numbers

From `coverage_reconciliation_report.json`:

- `eligible_positions`: `50`
- `clv_present_count`: `0`
- `clv_missing_count`: `50`
- `coverage_rate`: `0.0`

From `coverage_reconciliation_report.md` CLV section:

- `Coverage: 0.00% (0/50 eligible positions with CLV)`
- warning emitted: `CLV coverage below 30% (0.0%; 0/50).`

---

## Top Missingness Reasons

From `clv_coverage.missing_reason_counts`:

1. `OFFLINE`: `43`
2. `NO_CLOSE_TS`: `7`
3. `(none)`: no third non-zero reason

Notes:

- Run logs showed repeated CLOB `/prices-history` HTTP `400 Bad Request` responses.
- Audit report spot-check confirms explicit reason rendering per position (`N/A (OFFLINE)` and `N/A (NO_CLOSE_TS)`).

---

## Dossier/Audit Verification

- `dossier.json` positions include all CLV fields for all 50 rows:
  - `close_ts`, `close_ts_source`, `closing_price`, `closing_ts_observed`, `clv`, `clv_pct`, `beat_close`, `clv_source`, `clv_missing_reason`.
- `audit_coverage_report.md` includes CLV blocks per position with explicit reasons when null.

---

## Snapshot Table Counts

From ClickHouse `market_price_snapshots`:

- Global rows (`kind='closing'`): `0`
- Global distinct token IDs with closing snapshots: `0`
- Run token IDs in dossier: `50`
- Rows for this run token set: `0`
- Distinct run token IDs with at least one closing snapshot: `0`

Migration tracking:

- No migration-tracking table found (`SHOW TABLES LIKE '%migration%'` returned no rows).
- Migration state recorded by table existence + schema verification.

---

## Go/No-Go Decision for Roadmap 5.2

Decision: **NO-GO**.

Reason:

- Measured CLV coverage is `0.0%` (`0/50`), which is below the 30% threshold in SPEC/ADR stop criteria.
- Snapshot cache table remains empty for closing snapshots in this run (`0` rows).
- Missingness is dominated by `OFFLINE` and `NO_CLOSE_TS`, so advancing to 5.2 would add context logic without reliable closing-price signal coverage.

Suggested gate to re-evaluate 5.2:

- Demonstrate sustained CLV coverage >= 30% across consecutive runs and non-zero snapshot cache growth for resolved positions.

