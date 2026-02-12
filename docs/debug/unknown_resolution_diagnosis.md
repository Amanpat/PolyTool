# UNKNOWN Resolution Diagnosis (DrPufferfish)

Date: 2026-02-12  
Repo: PolyTool

## Exact Commands Run

```powershell
docker compose up -d --build clickhouse api

python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000" `
  --ingest-positions --compute-pnl --enrich-resolutions `
  --resolution-max-candidates 300 --resolution-batch-size 25 --resolution-max-concurrency 4 `
  --debug-export

# Step 2 helper (latest artifact discovery)
@'
from pathlib import Path
base = Path("artifacts/dossiers/users/drpufferfish")
run_dirs = [p for p in base.rglob("*") if p.is_dir() and (p / "run_manifest.json").exists()]
latest = max(run_dirs, key=lambda p: (p.stat().st_mtime, str(p)))
print(latest)
print(latest / "run_manifest.json")
print(latest / "coverage_reconciliation_report.json")
print(latest / "dossier.json")
'@ | python -

# Enrichment endpoint evidence
docker compose logs api | rg -n "Enriching resolutions|Resolution enrichment complete|POST /api/enrich/resolutions"

# ClickHouse evidence
docker compose exec -T clickhouse clickhouse-client -d polyttool -q "SHOW TABLES"
docker compose exec -T clickhouse clickhouse-client -d polyttool -q "SELECT count() AS total, countIf(settlement_price IS NOT NULL OR resolved_at IS NOT NULL) AS with_resolution_fields, countIf(resolution_source != '' AND resolution_source != 'unknown') AS with_named_source, max(fetched_at) AS latest_fetched_at FROM market_resolutions"
docker compose exec -T clickhouse clickhouse-client -d polyttool -q "SELECT count() AS rows_total, countIf(resolved_token_id!='') AS with_resolved_token_id, countIf(token_id!='') AS with_token_id, countIf(condition_id IS NOT NULL AND condition_id!='') AS with_condition_id FROM user_positions_resolved WHERE proxy_wallet='0xdb27bf2ac5d428a9c63dbc914611036855a6c56e' AND snapshot_ts=(SELECT max(snapshot_ts) FROM user_positions_resolved WHERE proxy_wallet='0xdb27bf2ac5d428a9c63dbc914611036855a6c56e')"
docker compose exec -T clickhouse clickhouse-client -d polyttool -q "SELECT name, engine FROM system.tables WHERE database='polyttool' AND name IN ('user_trade_lifecycle','user_trade_lifecycle_enriched') ORDER BY name"

# Regression tests touched
pytest -q tests/test_scan_trust_artifacts.py
```

## Diagnostic Snapshot (Baseline failing run)

Run used for diagnosis:
- `artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-12/6c3d1af8-ca36-4a7a-84f6-253bcd643c5a`

From `run_manifest.json`:
- `argv` includes `--enrich-resolutions`
- `git_commit`: `9020eae`
- `started_at`: `2026-02-12T21:47:07+00:00`
- `finished_at`: `2026-02-12T21:47:41+00:00`

From `coverage_reconciliation_report.json`:
- `resolution_coverage.unknown_resolution_rate`: `1.0`
- `fallback_uid_coverage.pct_with_fallback_uid`: `0.0`
- `deterministic_trade_uid_coverage.pct_with_trade_uid`: `0.0`
- `pnl.missing_realized_pnl_count`: `100`
- `outcome_counts.UNKNOWN_RESOLUTION`: `100`

From `dossier.json`:
- `positions.count`: `0`
- `len(positions.positions)`: `0`
- First 20 positions sample size: `0`
- Missing all identifiers in sample: `0` (no rows)

Enrichment runtime/API evidence:
- CLI summary: `candidates=300, processed=300, cached=286, written=0, unresolved=14, skipped_missing=0, errors=0`
- API log line: `POST /api/enrich/resolutions HTTP/1.1 200 OK`
- API log line: `Resolution enrichment complete ... candidates=300 cached=286 written=0 unresolved=14 ...`

ClickHouse evidence:
- `market_resolutions`: `total=286`, `with_resolution_fields=286`, `with_named_source=286`
- Latest snapshot in `user_positions_resolved` has identifiers: `rows_total=100`, `with_token_id=100`, `with_condition_id=100`, `with_resolved_token_id=61`
- Export lifecycle sources are missing: no `user_trade_lifecycle` / `user_trade_lifecycle_enriched` table in `polyttool`

## Root Cause (one sentence)

`scan` generated synthetic placeholder positions from count-only dossier metadata when lifecycle rows were absent, so coverage was computed over 100 empty dicts and forced `UNKNOWN_RESOLUTION=100%` even though enrichment ran and cache data existed.

## Smallest Fix Applied

1. `tools/cli/scan.py`
- Removed count-only placeholder fabrication in `_extract_positions_payload`.
- Added `_extract_declared_positions_count`.
- Added explicit warning + coverage warning entry when `declared_positions_count > 0` but exported position rows are `0`:
  - `dossier_declares_positions_count=... but exported positions rows=0. Likely lifecycle export/schema mismatch ...`

2. `tests/test_scan_trust_artifacts.py`
- Replaced the old fallback test with regression coverage for this failure mode:
  - asserts `positions_total == 0`
  - asserts warning is emitted and present in coverage report
  - asserts `unknown_resolution_rate == 0.0` (no fabricated UNKNOWN rows)

Why this works:
- It makes the failure impossible to miss (explicit warning with schema mismatch hint).
- It prevents false 100% UNKNOWN coverage caused by fabricated rows.

## Post-fix Verification

Fresh run after patch:
- `artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-12/786d2e68-e543-4a08-aea5-46ad7daacc10`
- `resolution_coverage.unknown_resolution_rate`: `0.0`
- Explicit stderr warnings printed:
  - `positions_total=0 ...`
  - `dossier_declares_positions_count=100 but exported positions rows=0 ...`

This confirms the false 100% UNKNOWN signal is removed and replaced by actionable diagnostics.
