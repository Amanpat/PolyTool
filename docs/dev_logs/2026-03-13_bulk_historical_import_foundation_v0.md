# Dev Log: Bulk Historical Import Foundation v0

**Date**: 2026-03-13
**Branch**: phase-1
**Objective**: Implement the foundation layer for Gate 2's import-first path as
specified by Master Roadmap v4.1. This shifts Gate 2 from "bounded live dislocation
capture" as the primary path to "bulk historical import first."

---

## What Was Built

### Python Package: `packages/polymarket/historical_import/`

- `__init__.py`: Package init with module docstring
- `manifest.py`: `ProvenanceRecord` and `ImportManifest` dataclasses with deterministic
  `manifest_id` (sha256 of source_kind + resolved_path). `make_provenance_record()` and
  `make_import_manifest()` factory functions. Three `SourceKind` enum values.
- `validators.py`: Three layout validators (`validate_pmxt_layout`,
  `validate_jon_becker_layout`, `validate_price_history_layout`). Each inspects the
  filesystem only — no file content reads, no network calls. Returns `ValidationResult`
  with `valid`, `file_count`, `checksum`, `errors`, `warnings`, and `notes`.

### CLI: `tools/cli/historical_import.py`

- `main(argv: Optional[list[str]]) -> int` pattern matching all existing CLI tools
- Two subcommands:
  - `validate-layout`: Dry-run layout check, exits 0 on success / 1 on failure
  - `show-manifest`: Generates and prints/writes provenance manifest JSON
- Registered as `import-historical` in `polytool/__main__.py`
- Listed under new "Data Import" section in `print_usage()`

### ClickHouse Migrations

Three new SQL files in `infra/clickhouse/initdb/`:
- `21_pmxt_archive.sql`: `polytool.pmxt_l2_snapshots` table (ReplacingMergeTree)
- `22_jon_becker_trades.sql`: `polytool.jb_trades` table (ReplacingMergeTree)
- `23_price_history_2min.sql`: `polytool.price_history_2min` table (ReplacingMergeTree)

All three tables grant SELECT to `grafana_ro`. All use `imported_at` as the
ReplacingMergeTree version key for idempotent re-import.

### Tests

- `tests/test_historical_import_manifest.py`: 17 tests covering determinism,
  schema version, source kind validation, destination tables, status values,
  JSON serialization, and multi-source manifests
- `tests/test_historical_import_validators.py`: 24 tests across three validator
  classes covering missing paths, empty directories, required vs optional
  subdirectories, file extension matching, warnings, and checksum determinism
- `tests/test_historical_import_cli.py`: 13 integration tests covering CLI
  subcommands, exit codes, stdout JSON structure, file writing, and determinism

### Docs

- `docs/specs/SPEC-0018-bulk-historical-import-foundation-v0.md`: Full spec covering
  purpose, three data sources, tape tier hierarchy (Gold/Silver/Bronze), provenance
  manifest contract, ClickHouse table schemas, validation contract, CLI reference,
  and kill conditions
- `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md`: Operator runbook covering download,
  extraction, validation, manifest generation, and deferred ClickHouse import
- `docs/dev_logs/2026-03-13_bulk_historical_import_foundation_v0.md`: This file

### Doc Patches

- `docs/CURRENT_STATE.md`: Updated Gate 2 status block, Track A section, and
  current operator focus to reflect import-first path
- `docs/ROADMAP.md`: Updated Track A current next step to name bulk historical
  import as primary path with live capture as fallback
- `docs/PLAN_OF_RECORD.md`: Added Gate 2 primary path row to the Roadmap Authority
  table (Section 0)

---

## Key Decisions

### Decision 1: Dry-run only (no import logic in this packet)

The `import-historical` CLI validates and documents but never loads data. This
keeps Packet 1 focused on the foundation layer and avoids premature ClickHouse
coupling. The import runner (with row-count verification and idempotent loading)
is Packet 2.

### Decision 2: Deterministic manifest_id

`manifest_id = sha256(f"{source_kind}:{resolved_absolute_path}")` ensures the
same source always produces the same ID across operator machines. This enables
idempotent re-validation without drift.

### Decision 3: Silver tapes are sufficient for Gate 2

Gate 2 tests strategy-level PnL logic (the scenario sweep), not live WS latency
or microstructure fidelity. Silver-tier tapes reconstructed from pmxt + jb_trades
+ price_history_2min are sufficient. Gate 3 (shadow mode) still requires Gold
tapes from live WS recording.

### Decision 4: Validators are filesystem-only

All three validators inspect directory structure and file names only. No content
parsing, no network calls. This makes them fast, offline-safe, and testable with
empty fixture files.

### Decision 5: jon_becker extension set

The Jon-Becker validator accepts `.parquet`, `.csv`, `.csv.gz`, and `.parquet.gz`.
This handles both the current distribution format and any future compression variants
without requiring a validator update.

---

## Test Results

All 54 new tests pass:
- `tests/test_historical_import_manifest.py`: 17/17
- `tests/test_historical_import_validators.py`: 24/24 (8 + 9 + 7)
- `tests/test_historical_import_cli.py`: 13/13

No regressions on existing test suite.

---

## What is NOT Done (Explicit Scope Boundary)

- Silver tape reconstruction: deferred to Packet 2
- ClickHouse import runner: deferred to Packet 2
- Gate 2 passage: not attempted; Gate 2 remains open
- `validated_at` field population: set by import runner (Packet 2)
- Multi-run delta detection: out of scope for foundation layer

---

## Next Packet Recommendation

**Packet 2: Silver Tape Reconstruction + ClickHouse Import Runner**

1. Implement ClickHouse import runner for all three sources with:
   - Row-count verification after load
   - Idempotent re-import (ReplacingMergeTree handles deduplication)
   - Manifest `validated_at` update after successful import
2. Implement Silver tape reconstruction:
   - Input: `polytool.pmxt_l2_snapshots` + `polytool.jb_trades` + `polytool.price_history_2min`
   - Output: `events.jsonl` tapes in the SimTrader replay format
   - Scope: L2 snapshot reconstruction for binary markets only
3. Validate that reconstructed tapes pass Gate 2 eligibility check
   (`sweeps/eligibility.py: executable_ticks > 0`)
4. Run Gate 2 scenario sweep on Silver-tier tapes
5. If sweep passes (>=70%), close Gate 2 via `tools/gates/close_sweep_gate.py`
