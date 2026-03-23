# Dev Log: Benchmark Gap-Fill Execution

**Date:** 2026-03-17
**Branch:** phase-1
**Packet:** Benchmark gap-fill execution (Packet 3 of Gate 2 path)

---

## Objective

Wire the operator flow for consuming `config/benchmark_v1_gap_fill.targets.json` and
batch-generating Silver tapes. The gap-fill planner (shipped earlier today) already
produced the targets manifest. This packet makes it executable.

---

## Files Changed

### `tools/cli/batch_reconstruct_silver.py`

**Why:** Extended with gap-fill execution mode (Mode 2). The existing batch runner
uses a shared window for all tokens; the targets manifest provides per-target windows.

Changes:
- Added `TARGETS_MANIFEST_SCHEMA = "benchmark_gap_fill_v1"` and `GAP_FILL_RUN_SCHEMA = "benchmark_gap_fill_run_v1"` constants
- Added `load_targets_manifest(path) -> (list, Optional[str])`: validates JSON,
  schema_version, and targets array; returns (targets, error) without raising
- Added `run_batch_from_targets(targets, ...)`: loops per target with its own window;
  skips invalid targets cleanly (missing token_id, bad window, inverted window);
  records per-target success/failure/skip in outcomes; reuses existing metadata
  persistence logic
- Added `_refresh_benchmark_curation(...)`: calls `_run_build()` from
  `benchmark_manifest.py`; never raises; returns machine-readable result dict
- Updated `_build_parser()`: `--window-start`/`--window-end` changed from
  `required=True` to `default=None` (validated at runtime per mode); added
  `--targets-manifest`, `--benchmark-refresh`, `--gap-fill-out`
- Updated `main()`: routes to `run_batch_from_targets` when `--targets-manifest` is
  set; original shared-window mode unchanged; benchmark refresh gated behind
  `not dry_run`

### `tests/test_batch_silver_gap_fill.py` (new)

**Why:** Focused tests for all new surfaces.

- `TestLoadTargetsManifest` (8 tests): valid, empty, wrong schema_version, missing
  targets key, not-a-dict, bad JSON, OSError, multiple targets
- `TestRunBatchFromTargets` (16 tests): single success, multiple, partial failure
  continues, skip invalid token_id, skip bad window, skip inverted window, skip
  non-dict entry, outcome carries bucket/slug, dry-run no files, deterministic output
  dir, schema_version, benchmark_refresh default, CH metadata success, JSONL fallback,
  empty targets, batch_run_id propagated, mixed success/skip/failure
- `TestBenchmarkRefreshHook` (5 tests): mocked manifest_written, mocked gap_report,
  internal error → error dict, real _run_build success, real _run_build rc=2
- `TestGapFillCLI` (10 tests): help, dry-run exits 0, missing file, bad schema,
  writes gap-fill result JSON, benchmark-refresh flag fires, refresh skipped on
  dry-run, mode 1 still works, mode 1 missing window start, all-skipped → exit 1

### `tests/test_batch_silver.py`

**Why:** `test_missing_window_start` expected `SystemExit` (argparse required arg).
Now `--window-start` is optional in parser; runtime check returns exit code 1 instead.

Change: `with pytest.raises(SystemExit)` → `rc = self._run(...)` + `assert rc != 0`

---

## Commands Run + Output

### Test run (all related tests)

```
python -m pytest tests/test_batch_silver.py tests/test_batch_silver_gap_fill.py \
    tests/test_benchmark_manifest.py tests/test_benchmark_gap_fill_planner.py \
    tests/test_silver_reconstructor.py -q --tb=short

190 passed in 11.75s
```

### Real dry-run smoke with actual targets manifest

```
python -m polytool batch-reconstruct-silver \
    --targets-manifest config/benchmark_v1_gap_fill.targets.json \
    --dry-run --skip-price-2min --skip-metadata

[batch-reconstruct-silver] [DRY-RUN] targets-manifest mode
  manifest: config\benchmark_v1_gap_fill.targets.json  targets=120
  out-root: artifacts
  batch_run_id: 6c32948e-...

[batch-reconstruct-silver] gap-fill complete
  targets_attempted: 120
  tapes_created: 120
  failure_count: 0
  skip_count: 0
  metadata: ch=0 jsonl=0 skipped=120
```

All 120 targets from the real manifest parsed and dispatched correctly.
confidence=none in dry-run (reconstructor not called for real).

---

## Real generation result

Dry-run only performed in this packet. Real generation requires:
1. `fetch-price-2min` for priority-1 token IDs (39 tokens: 9+11+10+9)
2. `batch-reconstruct-silver --targets-manifest config/benchmark_v1_gap_fill.targets.json --pmxt-root /data/raw/pmxt_archive --jon-root /data/raw/jon_becker`
3. `--benchmark-refresh` to trigger curation refresh

Expected outcome: 39 priority-1 tapes attempted (4 buckets × priorities).
`new_market` bucket (5 targets missing) will remain INSUFFICIENT.
`config/benchmark_v1.tape_manifest` will NOT be written until `new_market` is resolved.

---

## Whether benchmark_v1 was created

**No.** `new_market` bucket has 0 candidates in the current JB snapshot (stale by ~40
days). Quotas remain unmet. `config/benchmark_v1.tape_manifest` does not exist.
`config/benchmark_v1.gap_report.json` remains the authoritative status artifact.

---

## Operator command (production invocation)

```bash
# Step 1: populate price_2min for priority-1 token IDs
# (39 tokens; run fetch-price-2min for each or in batch)

# Step 2: batch Silver generation from targets manifest
python -m polytool batch-reconstruct-silver \
    --targets-manifest config/benchmark_v1_gap_fill.targets.json \
    --pmxt-root /data/raw/pmxt_archive \
    --jon-root  /data/raw/jon_becker \
    --benchmark-refresh \
    --gap-fill-out artifacts/silver/gap_fill_run_v1.json

# Inspect result
cat artifacts/silver/gap_fill_run_v1.json | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'tapes_created={d[\"tapes_created\"]} failure={d[\"failure_count\"]} skip={d[\"skip_count\"]}')
print(f'benchmark_refresh: {d[\"benchmark_refresh\"][\"outcome\"]}')
"
```
