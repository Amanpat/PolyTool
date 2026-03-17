# SPEC: Silver Tape Batch Generator v1

**Status:** Implemented — 2026-03-16
**Branch:** phase-1
**Implements:** `batch-reconstruct-silver` CLI, `tape_metadata` ClickHouse table, `silver_tape_metadata.py`

---

## 1. Purpose and Scope

This spec defines the operational v1 batch Silver tape generator. It extends the single-market
foundation (v0, SPEC-silver-reconstructor-v0.md) with:

- Batch reconstruction over multiple token IDs in a single command invocation
- Canonical output path layout using a 16-character token prefix
- `tape_metadata` persistence to ClickHouse after each successful reconstruction
- JSONL fallback when ClickHouse is unavailable
- Batch manifest JSON summarising all per-token outcomes

**In scope:**
- `tools/cli/batch_reconstruct_silver.py` — batch CLI
- `packages/polymarket/silver_tape_metadata.py` — metadata row builder and writers
- `infra/clickhouse/initdb/25_tape_metadata.sql` — DDL for `polytool.tape_metadata`

**Out of scope:**
- Gold tape generation (requires live WS recording, not reconstruction)
- ClickHouse bulk historical import (off critical path under v4.2)
- Parallelism / concurrent token processing

---

## 2. Batch CLI (`batch-reconstruct-silver`)

### Invocation

```bash
python -m polytool batch-reconstruct-silver \
    --token-id 0xAAA --token-id 0xBBB \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z" \
    --pmxt-root    /data/raw/pmxt_archive \
    --jon-root     /data/raw/jon_becker

# From file:
python -m polytool batch-reconstruct-silver \
    --token-ids-file tokens.txt \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z"
```

### Timestamp formats

Both `--window-start` and `--window-end` accept:
- ISO 8601 strings (with or without timezone, with or without trailing `Z`)
- Unix epoch floats (e.g. `1700000000.0`)

### Token ID inputs

Tokens may be provided via:
- One or more `--token-id ID` flags (repeatable)
- `--token-ids-file PATH`: one token per line; blank lines and lines starting with `#` are ignored

At least one token is required; the CLI exits 1 if none are provided.

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--out-root` | `artifacts` | Root directory for canonical output dirs |
| `--batch-out-dir` | `<out-root>/silver` | Where to write the batch manifest JSON |
| `--dry-run` | false | Fetch all data, skip all disk writes and metadata |
| `--skip-price-2min` | false | Skip ClickHouse price_2min query |
| `--skip-metadata` | false | Skip all tape_metadata writes |
| `--no-metadata-fallback` | false | Disable JSONL fallback when CH write fails |
| `--clickhouse-host` | `localhost` | ClickHouse host |
| `--clickhouse-port` | `8123` | ClickHouse HTTP port |
| `--clickhouse-user` | `polytool_admin` | ClickHouse user |
| `--clickhouse-password` | env `CLICKHOUSE_PASSWORD` or `polytool_admin` | CH password |

---

## 3. Canonical Output Path Format

Each token gets its own output directory:

```
<out-root>/silver/<token_id[:16]>/<YYYY-MM-DDTHH-MM-SSZ>/
```

- The `token_id[:16]` prefix uses the first 16 characters of the token ID hex string.
  This reduces collision risk in large batch runs (vs 8-char prefix in single-market CLI).
  If the token ID is shorter than 16 characters, the full token ID is used.
- The date component is derived from `window_start` in UTC.
- The separator in the date component is `-` (not `:`) to ensure path safety on all OSes.

**Example:**
```
artifacts/silver/0x1234567890abcdef/2024-01-01T00-00-00Z/
    silver_events.jsonl
    silver_meta.json
```

This path is deterministic: the same token_id + window_start always produces the same directory.

---

## 4. tape_metadata Schema

### ClickHouse Table: `polytool.tape_metadata`

```sql
CREATE TABLE IF NOT EXISTS polytool.tape_metadata
(
    run_id              String,           -- UUID per single reconstruction call
    tape_path           String,           -- Path to silver_events.jsonl
    tier                LowCardinality(String),  -- "silver"
    token_id            String,           -- Polymarket CLOB token ID
    window_start        DateTime64(3, 'UTC'),
    window_end          DateTime64(3, 'UTC'),
    reconstruction_confidence LowCardinality(String),  -- "high"|"medium"|"low"|"none"
    warning_count       UInt16,
    source_inputs_json  String,           -- JSON blob of SourceInputs
    generated_at        DateTime64(3, 'UTC'),
    batch_run_id        String            -- UUID shared across a batch run ("" if standalone)
)
ENGINE = ReplacingMergeTree(generated_at)
ORDER BY (tier, token_id, window_start)
SETTINGS index_granularity = 8192;
```

**Deduplication:** `ReplacingMergeTree(generated_at)` uses `generated_at` as the version key.
Re-running a batch for the same `(tier, token_id, window_start)` will produce a later `generated_at`,
which replaces the prior row during ClickHouse merges.

**Grafana access:** `GRANT SELECT ON polytool.tape_metadata TO grafana_ro` is included in the DDL.

### Python Dataclass: `TapeMetadataRow`

```python
@dataclass
class TapeMetadataRow:
    run_id: str
    tape_path: str
    tier: str                          # "silver"
    token_id: str
    window_start: str                  # ISO8601 UTC
    window_end: str                    # ISO8601 UTC
    reconstruction_confidence: str
    warning_count: int
    source_inputs_json: str            # JSON string
    generated_at: str                  # ISO8601 UTC
    batch_run_id: str                  # "" if not a batch run
```

### JSONL Fallback Record

When written to a JSONL file, one additional field is added:
```json
{
    "schema_version": "tape_metadata_v1",
    ... (all TapeMetadataRow fields)
}
```

---

## 5. ClickHouse Write + JSONL Fallback Behavior

### Write flow per token (after successful reconstruction)

```
reconstruct(token_id) -> SilverResult
  |
  if not skip_metadata and not dry_run and not result.error:
    build TapeMetadataRow from SilverResult
    attempt write_to_clickhouse(row)
      success -> meta_write_status = "clickhouse"
      failure and not no_metadata_fallback ->
        attempt write_to_jsonl(row, fallback_path)
          success -> meta_write_status = "jsonl_fallback"
          failure -> meta_write_status = "failed"
      failure and no_metadata_fallback ->
        meta_write_status = "failed_no_fallback"
  else:
    meta_write_status = "skipped"
```

### Error contract

Both `write_to_clickhouse` and `write_to_jsonl` **never raise exceptions**. They return `True` on
success and `False` on any error. This ensures metadata failures never abort the batch.

### Fallback path

Default fallback path: `<out-root>/silver_batch_metadata_fallback.jsonl`

Override with `--metadata-fallback-path` (programmatic API only; CLI uses the default).

---

## 6. Batch Manifest Schema (`silver_batch_manifest_v1`)

The batch manifest JSON is written to `<batch-out-dir>/batch_manifest_<batch_run_id[:8]>.json`.

### Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | `"silver_batch_manifest_v1"` |
| `batch_run_id` | string | UUID identifying this batch run |
| `started_at` | ISO8601 | UTC timestamp when batch started |
| `ended_at` | ISO8601 | UTC timestamp when batch completed |
| `dry_run` | bool | Whether `--dry-run` was active |
| `token_count` | int | Total tokens processed |
| `success_count` | int | Tokens with no reconstruction error |
| `failure_count` | int | Tokens that errored |
| `metadata_summary` | object | Aggregate metadata write counts (see below) |
| `window_start` | ISO8601 | Shared window start |
| `window_end` | ISO8601 | Shared window end |
| `out_root` | string | Output root path |
| `outcomes` | array | Per-token outcome objects (see below) |

### `metadata_summary` fields

| Field | Description |
|-------|-------------|
| `clickhouse` | Tokens whose metadata was written to ClickHouse |
| `jsonl_fallback` | Tokens whose metadata was written to JSONL fallback |
| `skipped` | Tokens where metadata write was skipped (dry-run, skip-metadata, or error) |

### Per-token outcome fields

| Field | Type | Description |
|-------|------|-------------|
| `token_id` | string | The token ID |
| `status` | string | `"success"` or `"failure"` |
| `reconstruction_confidence` | string | `"high"` \| `"medium"` \| `"low"` \| `"none"` |
| `event_count` | int | Total events in the Silver tape |
| `fill_count` | int | Jon-Becker fill events |
| `price_2min_count` | int | price_2min guide events |
| `warning_count` | int | Number of warnings |
| `warnings` | array | Warning message strings |
| `out_dir` | string or null | Output directory path |
| `events_path` | string or null | Path to silver_events.jsonl |
| `error` | string or null | Error message if status is "failure" |
| `metadata_write` | string | One of: `clickhouse`, `jsonl_fallback`, `failed`, `failed_no_fallback`, `skipped` |
| `metadata_write_detail` | string | Additional detail (e.g. fallback file path) |

---

## 7. Partial-Failure Behavior

The batch CLI processes tokens sequentially. Each token's reconstruction is wrapped in a
`try/except` that catches all exceptions. A token failure does NOT abort the batch.

- If a token raises an exception, `status="failure"`, `error=str(exc)`, and processing continues.
- If `SilverResult.error` is set (internal error), the token is marked as `status="failure"`.
- Metadata writes are only attempted for tokens where `status="success"`.

---

## 8. Exit Code Semantics

| Condition | Exit Code |
|-----------|-----------|
| All tokens succeeded (or mixed success/failure) | `0` |
| All tokens failed | `1` |
| Argument parsing error (missing required arg) | `2` (argparse default) |
| `--window-end <= --window-start` | `1` |
| No token IDs provided | `1` |
| `--token-ids-file` not readable | `1` |
| Invalid timestamp string | `1` |

**Note:** Metadata write failures (ClickHouse or JSONL) do NOT affect the exit code. They are
recorded in the manifest and do not count as token failures.

---

## 9. Programmatic API

```python
from tools.cli.batch_reconstruct_silver import run_batch, canonical_tape_dir

manifest = run_batch(
    token_ids=["0xAAA", "0xBBB"],
    window_start=1700000000.0,
    window_end=1700007200.0,
    out_root=Path("artifacts"),
    skip_metadata=True,          # offline mode
    _reconstructor_factory=my_factory,  # inject mock for testing
)
```

The `_reconstructor_factory` parameter is the primary test hook. It must be a callable that
accepts a `ReconstructConfig` and returns an object with a `.reconstruct()` method compatible
with `SilverReconstructor.reconstruct()`.

---

## 10. Related Documents

- `docs/specs/SPEC-silver-reconstructor-v0.md` — single-market foundation
- `docs/dev_logs/2026-03-16_silver_reconstructor_foundation_v0.md` — v0 implementation log
- `docs/dev_logs/2026-03-16_silver_reconstructor_operational_v1.md` — v1 implementation log
- `infra/clickhouse/initdb/24_price_2min.sql` — reference for ClickHouse DDL pattern
- `infra/clickhouse/initdb/25_tape_metadata.sql` — tape_metadata DDL
