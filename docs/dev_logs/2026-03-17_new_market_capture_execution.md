# Dev Log: New-Market Capture Execution v1

**Date:** 2026-03-17
**Branch:** phase-1

---

## Summary

Shipped the execution half of the new-market capture pipeline.  The planner
(`new-market-capture`) already produces `config/benchmark_v1_new_market_capture.targets.json`.
This packet implements `capture-new-market-tapes`, which consumes that manifest and
records a Gold tape for each target via the existing `TapeRecorder` surface.

---

## Files changed

| File | Action | Why |
|---|---|---|
| `tools/cli/capture_new_market_tapes.py` | **New** | Core CLI: loads manifest, resolves YES/NO tokens, calls TapeRecorder, writes metadata |
| `polytool/__main__.py` | **Updated** | Registered `capture-new-market-tapes` + `capture_new_market_tapes_main`; added help line |
| `tests/test_capture_new_market_tapes.py` | **New** | 45 offline tests (manifest loading, batch runner, refresh hook, CLI smoke) |
| `docs/specs/SPEC-new-market-capture-execution-v1.md` | **New** | Contract spec |
| `docs/dev_logs/2026-03-17_new_market_capture_execution.md` | **New** | This file |
| `docs/CURRENT_STATE.md` | **Updated** | Reflect shipped status and operator command |

---

## Design decisions

**Reuse TapeRecorder not ShadowRunner**: Gold tapes require only the raw WS event
stream, not live strategy execution.  `TapeRecorder` is the correct minimal surface;
it writes `raw_ws.jsonl`, `events.jsonl`, and `meta.json` — exactly what the tape
corpus and `tape-manifest` scanning expect.

**Re-resolve YES/NO token IDs at runtime**: The planner target carries only the first
`clobTokenId` (advisory).  At capture time, `MarketPicker.resolve_slug(slug)` provides
authoritative YES/NO mapping, identical to how `watch-arb-candidates` works.

**Reuse `tape_metadata` table with `tier="gold"`**: The existing ClickHouse schema
accepts any string in the `tier` column.  Gold tape rows carry
`reconstruction_confidence="gold"` and `source_inputs_json` with
`{"recorded_from_live_ws": true, ...}`.  No schema migration needed.

**`watch_meta.json` written before recording**: Same pattern as `watch_arb_candidates.py`.
Includes `regime="new_market"` so `tape_manifest.py`'s `_read_regime()` correctly
classifies the tape without relying on content analysis.

---

## Operator command added

```bash
# Full flow (planner → execute → refresh)
python -m polytool new-market-capture
python -m polytool capture-new-market-tapes \
    --targets-manifest config/benchmark_v1_new_market_capture.targets.json \
    --benchmark-refresh \
    --result-out artifacts/benchmark_capture/run.json

# Dry run (no WS connection, no files written)
python -m polytool capture-new-market-tapes --dry-run
```

---

## Test results

```
tests/test_capture_new_market_tapes.py  45 passed in 0.49s
tests/test_batch_silver_gap_fill.py     40 passed (unchanged)
tests/test_batch_silver.py              47 passed (unchanged)
```

All existing tests unaffected.  45 new tests cover:
- `TestLoadCaptureTargets` (8 tests): valid, wrong schema, missing key, bad JSON, OS error
- `TestCanonicalTapeDir` (3 tests): basic slug, slash in slug, empty slug
- `TestResolveBothTokenIds` (4 tests): success, exception, empty YES token, never raises
- `TestRunCaptureBatch` (17 tests): success, skip cases, failure, dry-run, metadata persistence, mixed outcomes
- `TestBenchmarkRefreshHook` (3 tests): manifest written, gap report, error path
- `TestCaptureCLI` (10 tests): help, missing manifest, bad schema, dry-run, result artifact, benchmark-refresh, exit codes

---

## Real capture result

**NOT run.** Live recording requires:
1. `config/benchmark_v1_new_market_capture.targets.json` — produced by running
   `python -m polytool new-market-capture` (requires live Gamma API access)
2. Polymarket WS connectivity for `TapeRecorder`

The targets file does not exist in this dev session (no live Gamma API call run).
Running `python -m polytool capture-new-market-tapes --dry-run` without the manifest
would produce exit 1 with: `Error: --targets-manifest: cannot read targets manifest: ...`

To generate the manifest first:
```bash
python -m polytool new-market-capture      # creates targets JSON (needs network)
python -m polytool capture-new-market-tapes --dry-run  # verify targets resoluble
python -m polytool capture-new-market-tapes --benchmark-refresh  # live recording
```

---

## Whether benchmark_v1.tape_manifest was created

**No.** `config/benchmark_v1.tape_manifest` was NOT created in this session.

The `new_market` quota (5 tapes) cannot be satisfied without live Gamma API access
and successful WS recording.  Per the gap-fill planner dev log (2026-03-17), the
Jon-Becker snapshot is ~40 days stale (no new_market candidates from historical data).
Live recording via `capture-new-market-tapes` is the only path to close this gap.

Current benchmark shortages (as of last `benchmark-manifest` run):
- politics: 9 remaining
- sports: 11 remaining
- crypto: 10 remaining
- near_resolution: 9 remaining
- new_market: 5 remaining

All buckets except `new_market` can be closed via `batch-reconstruct-silver --targets-manifest
config/benchmark_v1_gap_fill.targets.json` once `fetch-price-2min` populates the price_2min
ClickHouse table for the target token IDs.  `new_market` requires live capture.

---

## Next steps

1. Run `python -m polytool new-market-capture` (live Gamma API) to populate the targets manifest
2. Run `python -m polytool capture-new-market-tapes --dry-run` to verify slugs resolve
3. Run `python -m polytool capture-new-market-tapes --benchmark-refresh` to record tapes
4. Separately: run `fetch-price-2min` for gap-fill targets, then `batch-reconstruct-silver` for
   politics/sports/crypto/near_resolution buckets
