# Dev Log: Bulk Historical Import Execution v0 (Packet 2)

**Date**: 2026-03-13
**Branch**: phase-1
**Author**: Claude Code

---

## What Was Built

### `packages/polymarket/historical_import/importer.py` (NEW)

Core import execution engine for Phase 1. Provides:

- `ImportMode` enum: `DRY_RUN`, `SAMPLE`, `FULL`
- `ImportResult` dataclass with full counters, timestamps, error lists, and `to_dict()`
- `CHInsertClient` protocol for type-safe, injectable ClickHouse client
- `ClickHouseClient` — wraps `clickhouse_connect`; lazy-connects on first insert
- `PmxtImporter` — reads Parquet files under `<path>/Polymarket/`, maps columns, inserts to `polytool.pmxt_l2_snapshots`
- `JonBeckerImporter` — reads CSV/CSV.GZ/Parquet under `<path>/data/polymarket/trades/`, inserts to `polytool.jb_trades`
- `PriceHistoryImporter` — reads JSONL/JSON/CSV files (one per token_id), inserts to `polytool.price_history_2min`
- `run_import()` dispatch function — validates source_kind, auto-generates run_id, propagates snapshot_version/notes

### `packages/polymarket/historical_import/manifest.py` (UPDATED)

Added `ImportRunRecord` dataclass and `make_import_run_record()` factory:

- `schema_version = "import_run_v0"` on all records
- All ImportResult fields mapped into ImportRunRecord
- `provenance_hash` field populated via `provenance.py` integration (see below)
- `to_dict()` and `to_json()` serialization

### `tools/cli/historical_import.py` (UPDATED)

Added `import` subcommand with full argument surface:

- `--source-kind`, `--local-path`, `--import-mode` (default: `dry-run`)
- `--sample-rows`, `--run-id`, `--snapshot-version`, `--notes`
- `--out` (write JSON run record)
- `--ch-host/port/user/password` (override via env vars CLICKHOUSE_HOST/PORT/USER/PASSWORD)

Handler (`_cmd_import`):
1. Runs layout validation; aborts non-dry-run on invalid layout
2. Builds CH client only for sample/full modes
3. Calls `run_import()`, builds `ImportRunRecord`, prints summary table
4. Writes JSON run record if `--out` specified
5. Returns 0 on dry-run/complete, 1 on failed/partial

---

## Provenance.py Integration Decision

**Decision: INTEGRATE.**

`make_import_run_record()` calls `build_deterministic_import_manifest_id()` from
`provenance.py` to compute the `provenance_hash` field on each `ImportRunRecord`.

Rationale:
- The import mode (dry-run vs. sample vs. full) is included in the hash payload,
  so dry-run and full import records get different IDs — enabling auditors to
  distinguish exploratory runs from production imports.
- Validates all required provenance fields before computing, catching schema drift
  at import time.
- Reuses the alias resolution logic already tested in
  `test_historical_import_provenance.py` (no new hashing code).

The Packet 1 `ProvenanceRecord.manifest_id` (sha256 of source_kind:path) is
retained as-is for the layout-validation tier. The `provenance_hash` on
`ImportRunRecord` is a separate, import-mode-aware identifier for the
execution tier.

---

## Key Decisions

1. **Dry-run is the default and safest mode.** The `--import-mode` argument
   defaults to `"dry-run"`. Operators must explicitly pass `sample` or `full`
   to write to ClickHouse.

2. **pyarrow is optional.** Added as `historical-import` extra in `pyproject.toml`.
   CSV and JSONL paths require no additional dependencies. If pyarrow is not
   importable and a Parquet file is encountered, an `ImportError` is raised
   with an actionable install message. Dry-run mode never reads file contents
   so it always works regardless of pyarrow availability.

3. **CH client is injectable for testing.** All three importer classes accept
   `ch_client` as a keyword argument. The `MockCHClient` in tests accumulates
   calls without touching a real database. `ClickHouseClient` is only
   instantiated by the CLI handler and only for non-dry-run modes.

4. **provenance.py integrated for import-mode-sensitive manifest ID.** The
   `source_state` field passed to provenance is `"complete"` for
   `dry-run`/`complete` completeness and `"partial"` for partial/failed runs.
   This allows Gate 2 audit tooling to verify that the full import record
   has a different provenance_hash than any dry-run record.

5. **Column mapping is try-first-found.** Each importer defines candidate
   column name lists in priority order (most common name first). This makes
   the engine robust to schema variation across dataset versions without
   requiring per-version adapters. Missing columns default to `""` or `0.0`.

6. **Per-file error isolation.** Exceptions from one file are caught, appended
   to `result.errors`, and processing continues to the next file.
   `import_completeness` is set to `"partial"` if any errors occurred, `"complete"`
   if none. This prevents one corrupt file from aborting a multi-thousand-file
   import run.

---

## Test Results

New test files:
- `tests/test_historical_import_importer.py` — covers dry-run, CSV sample/full,
  JSONL sample/full, dispatch, to_dict, missing paths, ImportRunRecord integration
- `tests/test_historical_import_cli.py` — extended with `TestImportCLI` (8 new tests)

All pre-existing historical import tests continue to pass:
- `test_historical_import_manifest.py`
- `test_historical_import_validators.py`
- `test_historical_import_cli.py`
- `test_historical_import_provenance.py`

---

## NOT Done

- Silver tape reconstruction from pmxt + jb_trades + price_history_2min
  (Packet 3 scope)
- Gate 2 passage — requires Silver tapes + scenario sweep >=70%
- Idempotent re-import / deduplication (ReplacingMergeTree handles this at
  the DB level; no application-level dedup implemented)
- Kalshi/Opinion import paths in PmxtImporter are stubbed (platform name
  detected from directory; import logic is identical to Polymarket path)

---

## Next Packet Recommendation: Silver Tape Reconstruction

With the three source tables populated (`pmxt_l2_snapshots`, `jb_trades`,
`price_history_2min`), the next packet should implement Silver tape
reconstruction:

1. Join `pmxt_l2_snapshots` + `jb_trades` + `price_history_2min` by
   `token_id` and time window
2. Emit deterministic `events.jsonl` tapes in SimTrader format
3. Verify tapes pass Gate 2 eligibility checks (`executable_ticks > 0`)
4. Run `close_sweep_gate.py` if sweep score >= 70%
