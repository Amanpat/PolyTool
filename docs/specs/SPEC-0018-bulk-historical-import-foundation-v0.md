# SPEC-0018: Bulk Historical Import Foundation v0

**Status**: Shipped (2026-03-13)
**Branch**: phase-1
**Supersedes**: None
**Related**: ROADMAP.md Track A, PLAN_OF_RECORD.md Section 0

---

## 1. Purpose and Context

Master Roadmap v4.1 changes Gate 2's primary path from "bounded live dislocation
capture" to "bulk historical import first." The live-capture path remains a valid
fallback when a catalyst window fires, but the primary unblocking strategy is now:

1. Import historical L2 snapshot data from the pmxt archive
2. Import the Jon-Becker 72M-trade Polymarket dataset
3. Pull 2-minute price history via the polymarket-apis PyPI package
4. Reconstruct Silver-tier tapes from the above (Packet 2, not this spec)
5. Run the Gate 2 scenario sweep on Silver-tier tapes

This spec covers the **foundation layer** only: provenance manifests, local-path
layout validators, destination ClickHouse table schemas, and the dry-run CLI
(`import-historical`). Actual data loading into ClickHouse is deferred to Packet 2.

Gate 2 is NOT passed by this spec. Silver tape reconstruction is NOT shipped by
this spec.

---

## 2. Three Data Sources

### 2.1 pmxt_archive

- **URL**: https://archive.pmxt.dev
- **Format**: Parquet files, organized by exchange under `Polymarket/`, `Kalshi/`,
  and `Opinion/` subdirectories
- **Content**: Hourly L2 orderbook snapshots (bids and asks by price level)
- **License**: Check archive.pmxt.dev terms before use
- **Destination table**: `polytool.pmxt_l2_snapshots`
- **Value for Gate 2**: Provides historical depth data to reconstruct the orderbook
  state at any point in time. Silver-tier tapes built from this source are sufficient
  for strategy-level PnL tests (Gate 2), though not for microstructure analysis.

### 2.2 jon_becker

- **URL**: s3.jbecker.dev/data.tar.zst (see prediction-market-analysis repo)
- **Format**: `data.tar.zst` archive; after extraction: `data/polymarket/trades/`
  contains Parquet or CSV files
- **Content**: 72.1M Polymarket trades with fields: timestamp, price (1-99c), size,
  taker_side, resolution, category
- **License**: MIT
- **Destination table**: `polytool.jb_trades`
- **Value for Gate 2**: Provides a rich historical trade corpus for realistic
  market simulation. Allows Silver-tier tape construction without live recording.

### 2.3 price_history_2min

- **Source**: polymarket-apis PyPI package
- **Method**: `get_all_price_history_by_token_id(token_id)` (public, no API key)
- **Format**: One `.jsonl` or `.csv` file per token_id in a local directory
- **Content**: Price at 2-minute intervals for each token
- **Destination table**: `polytool.price_history_2min`
- **Value for Gate 2**: Provides price trajectory data for mid-price estimation
  and spread estimation when building Silver-tier tapes.

---

## 3. Tape Tier Hierarchy

| Tier | Source | Contents | Gate 2 eligible | Gate 3 eligible |
|------|--------|----------|-----------------|-----------------|
| Gold | Live WS recording | Real-time L2 ticks, exact timing, latency-accurate | Yes | Yes |
| Silver | Reconstructed from pmxt + jb_trades + price_history | Approximate L2 ticks, price-accurate, timing reconstructed | Yes | No |
| Bronze | Price history only | Mid-price only, no depth | No | No |

Gate 2 requires Silver or Gold. Gate 3 (shadow mode) requires Gold only.

The distinction matters: a Silver tape can pass the scenario sweep (Gate 2) because
the sweep tests strategy-level PnL logic, not live-WS latency or microstructure
fidelity. Gate 3 shadow mode requires a live WS connection and cannot use Silver tapes.

---

## 4. Provenance Manifest Contract

Each import is documented with a `ProvenanceRecord` before any data is loaded.
The manifest is deterministic: the same source kind and path always produce the
same `manifest_id`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Always `"import_manifest_v0"` |
| `manifest_id` | string | `sha256(f"{source_kind}:{resolved_absolute_path}")` (64 hex chars) |
| `source_kind` | string | One of: `pmxt_archive`, `jon_becker`, `price_history_2min` |
| `local_path` | string | As provided by the operator |
| `resolved_path` | string | `Path(local_path).resolve()` — absolute |
| `destination_tables` | list[str] | ClickHouse tables this source populates |
| `snapshot_version` | string | Optional operator-supplied label (e.g. `"2026-03"`) |
| `file_count` | int | Number of data files found by the validator |
| `checksum` | string | `sha256` of sorted file names |
| `status` | string | `"staged"` (layout invalid) or `"validated"` (layout valid) |
| `created_at` | ISO-8601 | When the record was created |
| `validated_at` | ISO-8601 | Set by the import runner when data is loaded (empty until then) |
| `notes` | string | Free-form notes |

### Status Values

- `staged`: Layout validation failed; data cannot be imported yet.
- `validated`: Layout validation passed; ready for import.
- `imported`: Import runner has loaded data (set by Packet 2 import runner, not this spec).
- `failed`: Import attempted but failed (set by Packet 2 import runner).

---

## 5. ClickHouse Destination Tables

All three tables use `ReplacingMergeTree(imported_at)` for idempotent re-import.
Tables are created by migration scripts in `infra/clickhouse/initdb/`.

| Table | Migration | Description |
|-------|-----------|-------------|
| `polytool.pmxt_l2_snapshots` | `21_pmxt_archive.sql` | pmxt hourly L2 snapshots |
| `polytool.jb_trades` | `22_jon_becker_trades.sql` | Jon-Becker 72M trades |
| `polytool.price_history_2min` | `23_price_history_2min.sql` | 2-minute price history |

`grafana_ro` has SELECT on all three tables.

The `import_run_id` column in each table enables traceability back to a specific
import run. The `source_file` column records which file each row came from.

---

## 6. Dry-Run Validation Contract

The `validate-layout` subcommand checks only the filesystem. It never reads file
contents, never makes network calls, and never writes to ClickHouse.

### pmxt_archive validation

- Required: `<local_path>/Polymarket/` directory exists
- Required: `Polymarket/` contains at least one `*.parquet` file (recursive)
- Optional: `Kalshi/` and `Opinion/` subdirectories (counted if present)
- Error if `Polymarket/` is missing or empty
- Notes list optional subdirectory file counts

### jon_becker validation

- Required: `<local_path>/data/polymarket/trades/` directory exists
- Required: that directory contains at least one `.parquet`, `.csv`, `.csv.gz`,
  or `.parquet.gz` file (recursive)
- Optional: `data/kalshi/trades/` (counted if present)
- Warning (not error) if `data.tar.zst` exists but `data/` is not extracted
- Error if `data/polymarket/trades/` is missing or empty

### price_history_2min validation

- Required: `<local_path>/` contains at least one `.jsonl`, `.csv`, or `.json` file
  (recursive)
- Error if no qualifying files found

### Checksum

Each validator computes `sha256(sorted_file_names_joined_by_newline)`. This checksum
is stable across runs on the same directory but changes if files are added or removed.
It is stored in the provenance manifest for audit purposes.

---

## 7. CLI Reference

```
python -m polytool import-historical <SUBCOMMAND> [OPTIONS]

Subcommands:
  validate-layout   Check local directory layout (dry-run, no import, no ClickHouse)
  show-manifest     Generate and print a JSON provenance manifest

validate-layout options:
  --source-kind KIND     Required. One of: jon_becker, pmxt_archive, price_history_2min
  --local-path PATH      Required. Path to the local data directory.

show-manifest options:
  --source-kind KIND     Required. One of: jon_becker, pmxt_archive, price_history_2min
  --local-path PATH      Required. Path to the local data directory.
  --snapshot-version V   Optional. Label to embed (e.g. "2026-03").
  --notes TEXT           Optional. Free-form notes to embed.
  --out PATH             Optional. Write JSON to file; print to stdout if omitted.

Exit codes:
  0   Layout valid (validate-layout) or manifest written for valid layout (show-manifest)
  1   Layout invalid, path missing, or manifest written for invalid layout

Examples:
  python -m polytool import-historical validate-layout \
      --source-kind pmxt_archive --local-path /data/pmxt

  python -m polytool import-historical show-manifest \
      --source-kind pmxt_archive --local-path /data/pmxt \
      --snapshot-version "2026-03" \
      --out artifacts/imports/pmxt_manifest.json
```

---

## 8. Kill Conditions

The following are explicitly OUT OF SCOPE for this spec:

- **No Silver tape reconstruction**: Building Silver-tier tapes from the imported
  data is Packet 2. Do not implement tape reconstruction here.
- **No Gate 2 marking**: This spec does not pass Gate 2. Gate 2 requires a passing
  scenario sweep artifact at `artifacts/gates/sweep_gate/gate_passed.json`.
- **No ClickHouse import**: The `import-historical` CLI does not write to ClickHouse.
  All ClickHouse loading is deferred to Packet 2.
- **No live data fetching**: All commands are filesystem-only. No HTTP calls.
- **No Gold tape downgrade**: Silver tapes must not be used for Gate 3 (shadow mode).
  Gate 3 requires live WS recording.

---

## 9. Implementation Files

| File | Role |
|------|------|
| `packages/polymarket/historical_import/__init__.py` | Package init |
| `packages/polymarket/historical_import/manifest.py` | ProvenanceRecord, ImportManifest, make_* helpers |
| `packages/polymarket/historical_import/validators.py` | validate_pmxt_layout, validate_jon_becker_layout, validate_price_history_layout |
| `tools/cli/historical_import.py` | CLI entrypoint (main(argv) -> int) |
| `infra/clickhouse/initdb/21_pmxt_archive.sql` | pmxt_l2_snapshots DDL |
| `infra/clickhouse/initdb/22_jon_becker_trades.sql` | jb_trades DDL |
| `infra/clickhouse/initdb/23_price_history_2min.sql` | price_history_2min DDL |
| `tests/test_historical_import_manifest.py` | Manifest unit tests |
| `tests/test_historical_import_validators.py` | Validator unit tests |
| `tests/test_historical_import_cli.py` | CLI integration tests |
| `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` | Operator runbook |
