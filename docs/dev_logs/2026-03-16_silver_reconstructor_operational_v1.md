# Dev Log: Silver Reconstructor Operational v1

**Date:** 2026-03-16
**Branch:** phase-1
**Status:** Complete — 47/47 new tests passing, 58/58 existing tests still passing, CLI smoke passing

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `infra/clickhouse/initdb/25_tape_metadata.sql` | Created | DDL for `polytool.tape_metadata` table; persists Silver reconstruction metadata to CH |
| `packages/polymarket/silver_tape_metadata.py` | Created | `TapeMetadataRow` dataclass, `build_from_silver_result`, `write_to_clickhouse`, `write_to_jsonl` |
| `tools/cli/batch_reconstruct_silver.py` | Created | `batch-reconstruct-silver` CLI; batch loop, canonical path, metadata writes, manifest output |
| `tests/test_batch_silver.py` | Created | 47 offline tests covering all batch behavior, CLI, metadata row, schema |
| `docs/specs/SPEC-silver-tape-batch-v1.md` | Created | Spec doc for batch Silver generation contract |
| `polytool/__main__.py` | Modified | Registered `batch-reconstruct-silver` command and added to Data Import help section |
| `docs/CURRENT_STATE.md` | Modified | Updated Silver tape status from "not yet started" to v0+v1 shipped |

---

## What Was Implemented

### `tape_metadata` ClickHouse Table (25_tape_metadata.sql)

- `ReplacingMergeTree(generated_at)` on `(tier, token_id, window_start)` — re-runs replace older rows during merges
- `LowCardinality` on `tier` and `reconstruction_confidence` — efficient for small cardinality string columns
- `GRANT SELECT ... TO grafana_ro` included for dashboard access
- Follows the same DDL pattern as `24_price_2min.sql`

### `silver_tape_metadata.py`

- `TapeMetadataRow` dataclass with all fields matching the CH schema
- `to_ch_row()` converts ISO8601 strings to epoch milliseconds for `DateTime64(3, 'UTC')` columns
- `build_from_silver_result()` extracts all required fields from `SilverResult.to_dict()` — no direct attribute access, so it works with both real and stub results
- `write_to_clickhouse()` — raw `urllib.request` POST, basic auth, 10s timeout; never raises
- `write_to_jsonl()` — appends one JSONL record with `schema_version` field; never raises

### `batch_reconstruct_silver.py`

- `canonical_tape_dir()` — 16-char token prefix, UTC date label with `-` separators for path safety
- `run_batch()` — sequential per-token reconstruction loop with full exception isolation
- Metadata write flow: attempt CH -> fall back to JSONL -> respect `no_metadata_fallback`
- Module-level imports of `SilverReconstructor` and `write_to_clickhouse` enable `unittest.mock.patch`
  targeting (lazy imports inside `run_batch` would break patch targets)
- `_reconstructor_factory` parameter for test injection (same pattern as `_pmxt_fetch_fn` etc. in v0)
- Batch manifest schema `silver_batch_manifest_v1` with all per-token outcome fields
- Exit 1 only when ALL tokens fail; partial failure is exit 0

### `__main__.py` Changes

- Added `batch_reconstruct_silver_main` endpoint
- Added `"batch-reconstruct-silver"` to `_COMMAND_HANDLER_NAMES`
- Added help text under `--- Data Import ---` section after `reconstruct-silver`

---

## Deviations from Plan

### [Rule 1 - Bug] Module-level imports for mock patch compatibility

**Found during:** Test implementation (TestRunBatch.test_jsonl_fallback_when_ch_fails)

**Issue:** The plan specified lazy imports inside `run_batch()`. `unittest.mock.patch` requires
symbols to be importable at the module level of the target module (it patches the name binding
in the target module's namespace). Lazy imports inside a function create local bindings that
cannot be patched via `patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse")`.

**Fix:** Moved `SilverReconstructor`, `write_to_clickhouse`, `write_to_jsonl`, and related
imports to module level with a `try/except ImportError` guard. This preserves testability while
keeping the module importable in environments where dependencies are not installed.

**Files modified:** `tools/cli/batch_reconstruct_silver.py`

### [Rule 1 - Bug] Windows path separator in test

**Found during:** Test run on Windows

**Issue:** `test_build_uses_events_path_when_tape_path_empty` compared
`str(Path("/some/path/silver_events.jsonl"))` as a string. On Windows, `Path.str()` returns
backslashes, so the comparison `== "/some/path/silver_events.jsonl"` failed.

**Fix:** Changed the assertion to use `Path(row.tape_path) == Path("/some/path/silver_events.jsonl")`
for cross-platform correctness.

**Files modified:** `tests/test_batch_silver.py`

---

## Test Results

### New tests (47/47 passing):

| Class | Count | What it covers |
|-------|-------|----------------|
| `TestCanonicalTapeDir` | 8 | Path format, 16-char prefix, short token, determinism, date label, unknown token |
| `TestRunBatch` | 11 | Single/multiple tokens, partial/all fail, dry-run, skip metadata, CH fallback, no-fallback, batch_run_id, error field, token order, CH success count |
| `TestBatchManifestSchema` | 5 | Required top-level keys, schema_version, outcome keys, ISO timestamps, metadata_summary keys |
| `TestTapeMetadataRow` | 10 | build_from_silver_result, empty warnings, CH row keys, epoch ms types, JSONL write/append/bad-path, source_inputs JSON, tape_path resolution |
| `TestBatchCLI` | 13 | --help, missing token, missing window-start, window ordering, dry-run, token-ids-file, invalid timestamp, all-fail exit code, epoch TS, manifest file written, missing file, skip-metadata, partial failure |

### Existing tests still passing (58/58):
```
tests/test_silver_reconstructor.py: 58 passed
```

---

## CLI Smoke Output

```
python -m polytool batch-reconstruct-silver --help
```

Exits 0 and shows full usage with all flags documented (see actual output above).

---

## Known Limitations

1. **Sequential processing only.** Tokens are processed one at a time in the order provided.
   For large batches (100+ tokens), this may be slow. Parallelism is not in scope for v1.

2. **Single shared time window.** All tokens in a batch run share the same `--window-start` /
   `--window-end`. For multi-window batch runs, call the CLI multiple times.

3. **No retry on CH failure.** If ClickHouse is temporarily unavailable, the JSONL fallback
   captures the metadata row. There is no automatic retry or backfill from the fallback file.

4. **16-char prefix still has collision risk.** Two token IDs with identical first 16 characters
   in the same batch run would write to the same directory. This is unlikely with Polymarket
   CLOB token IDs (which are Keccak-256 hashes) but is not impossible. The canonical path
   is deterministic and idempotent; a second reconstruction overwrites the first.
