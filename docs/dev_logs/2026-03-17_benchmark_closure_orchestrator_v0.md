# Dev Log: Benchmark Closure Orchestrator v0

**Date:** 2026-03-17
**Branch:** phase-1
**Spec:** `docs/specs/SPEC-benchmark-closure-orchestrator-v1.md`

---

## Objective

Build `close-benchmark-v1` — a single CLI command that orchestrates the full
benchmark_v1 tape closure sequence: preflight → Silver gap-fill →
new-market capture → benchmark curation refresh → closure status artifact.

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `tools/cli/close_benchmark_v1.py` | Created | Orchestrator module |
| `tests/test_close_benchmark_v1.py` | Created | 23 offline tests |
| `polytool/__main__.py` | Modified | Register `close-benchmark-v1` command + usage help |
| `docs/specs/SPEC-benchmark-closure-orchestrator-v1.md` | Created | Contract spec |
| `docs/dev_logs/2026-03-17_benchmark_closure_orchestrator_v0.md` | Created | This file |
| `docs/CURRENT_STATE.md` | Modified | Status update |

---

## Architecture

The orchestrator (`tools/cli/close_benchmark_v1.py`) is a pure Python module
with four stage functions + a top-level `run_closure()` that drives them in
sequence.  No subprocess spawning — all downstream CLIs are called as Python
functions.

**Reused surfaces (no duplication):**
- `run_batch_from_targets()` + `_refresh_benchmark_curation()` from
  `tools.cli.batch_reconstruct_silver`
- `main()` from `tools.cli.fetch_price_2min` (injectable for tests)
- `main()` from `tools.cli.new_market_capture` (injectable)
- `main()` from `tools.cli.capture_new_market_tapes` (injectable)

**Stage isolation:** each stage captures its own outcome dict; a failure in one
stage does not erase prior state or abort the run.

**Resumability:** if `config/benchmark_v1.tape_manifest` already exists at
preflight time, the orchestrator immediately exits 0 without touching anything.

---

## Orchestration Stages Implemented

1. **Preflight** — checks manifest existence, gap-fill targets manifest, CH
   availability, priority-1 target count, live-connectivity warning for
   new-market stage.
2. **Silver gap-fill** — loads targets, calls `fetch-price-2min` for priority-1
   tokens, calls `run_batch_from_targets`, calls `_refresh_benchmark_curation`.
3. **New-market closure** — calls `new-market-capture` planner; if candidates
   exist, calls `capture-new-market-tapes --benchmark-refresh`; checks artifact
   state to determine refresh outcome.
4. **Finalization** — validates manifest or reads gap report shortages +
   new-market insufficiency to surface deterministic blocker messages.

---

## Run Artifact

Schema `benchmark_closure_run_v1`.  Written to:
```
artifacts/benchmark_closure/<YYYY-MM-DD>/<run_id>/benchmark_closure_run_v1.json
```
Override with `--out PATH`.

---

## Commands Run + Output

### Test suite
```
pytest tests/test_close_benchmark_v1.py -v --tb=short
```
Result: **23 passed** (1 failure fixed: `_read_gap_report` default arg was
bound at definition time, not call time — fixed by passing `GAP_REPORT_PATH`
explicitly from `run_finalization`).

### Real dry-run
```
python -m polytool close-benchmark-v1 --dry-run \
  --out artifacts/benchmark_closure/2026-03-17/dry_run_smoke/benchmark_closure_run_v1.json
```

Output:
```
[close-benchmark-v1] starting run
  mode: DRY-RUN (no mutations)

Stage 1: Preflight
  [WARNING] ClickHouse not reachable at localhost:8123
  [WARNING] new-market stage requires live Gamma API and WS connectivity
  [OK] preflight passed

Stage 2: Silver gap-fill
  status: dry_run

Stage 3: New-market closure
  status: dry_run

Stage 4: Finalization
  final_status: blocked
  [BLOCKER] bucket 'politics': shortage=9
  [BLOCKER] bucket 'sports': shortage=11
  [BLOCKER] bucket 'crypto': shortage=10
  [BLOCKER] bucket 'near_resolution': shortage=9
  [BLOCKER] bucket 'new_market': shortage=5
```

Exit code: 1 (blocked — correct, no mutations in dry-run).
Artifact path: `artifacts/benchmark_closure/2026-03-17/dry_run_smoke/benchmark_closure_run_v1.json`

### Key artifact fields from dry-run
- `dry_run: true`
- `final_status: "blocked"`
- `preflight.status: "ready"` (gap-fill targets found; CH offline is a warning not a blocker)
- `preflight.checks.gap_fill_priority1_count: 39`
- `silver_gap_fill.fetch_price_2min.planned_tokens`: 39 priority-1 token IDs listed
- `finalization.blockers`: 5 per-bucket shortage messages derived from real gap report

---

## Existing Tests

No regressions. The orchestrator tests are fully isolated and do not touch any
prior test files.

---

## What Remains Before benchmark_v1 Is Real

1. **Docker up + price_2min fetch** — start CH + run `fetch-price-2min` for the
   39 priority-1 token IDs listed in the dry-run artifact.
2. **Live Silver run** — `close-benchmark-v1 --skip-new-market --pmxt-root
   <path> --jon-root <path>` to reconstruct Silver tapes for politics / sports /
   crypto / near_resolution buckets.
3. **new-market capture** — run `close-benchmark-v1 --skip-silver` during a
   window when Polymarket has fresh listings (<48h); requires live WS.
4. **Full closure** — run `close-benchmark-v1` (no skips) once both Silver and
   new-market data are populated; expect exit 0 and
   `config/benchmark_v1.tape_manifest` to appear.
