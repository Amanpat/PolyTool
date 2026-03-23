# Dev Log: Benchmark Closure Operator Readiness v0

**Date:** 2026-03-17
**Branch:** phase-1
**Spec:** `docs/specs/SPEC-benchmark-closure-operator-readiness-v0.md`

---

## Objective

Reduce operator error for the real benchmark_v1 closure run by adding three
operator-facing surfaces to the existing orchestrator:

1. `--status` flag — single-command progress snapshot
2. `--export-tokens` flag — deterministic export of 39 priority-1 token IDs
3. A canonical runbook at `docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md`

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `tools/cli/close_benchmark_v1.py` | Modified | Added `run_status()`, `run_export_tokens()`, `_find_latest_run_artifact()`; added `PRIORITY1_TOKENS_TXT`, `PRIORITY1_TOKENS_JSON` path constants; added `--status` and `--export-tokens` to parser and `main()` |
| `tests/test_benchmark_closure_operator.py` | Created | 17 offline tests covering new operator surfaces |
| `docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md` | Created | Canonical 7-step closure runbook with resumability guidance |
| `docs/specs/SPEC-benchmark-closure-operator-readiness-v0.md` | Created | Contract spec for the new surfaces |
| `docs/dev_logs/2026-03-17_benchmark_closure_operator_readiness_v0.md` | Created | This file |
| `docs/CURRENT_STATE.md` | Modified | Added operator-readiness entry |

---

## Operator Helper Surfaces Added

### `--status` (always safe, read-only, exit 0)

```
python -m polytool close-benchmark-v1 --status
```

Shows a fixed-width table:
- `Manifest:` — CREATED or MISSING
- `Gap-fill targets:` — FOUND (N targets, M priority-1) or MISSING
- `Token export (.txt/.json):` — FOUND or MISSING
- `New-market targets:` — FOUND or MISSING
- `Latest run:` — date + run-dir + [status, dry_run=T/F]
- `Residual blockers:` — per-bucket shortages from gap report
- `Suggested next step:` — adaptive single-line or multi-line guidance

### `--export-tokens` (deterministic, idempotent, exit 0 on success)

```
python -m polytool close-benchmark-v1 --export-tokens
```

Reads `config/benchmark_v1_gap_fill.targets.json`, filters `priority == 1`,
writes:
- `config/benchmark_v1_priority1_tokens.txt` — 39 tokens, one per line
- `config/benchmark_v1_priority1_tokens.json` — same as JSON array

Priority-2 overflow targets are excluded. Output is deterministic and always
matches the real gap-fill planner's priority-1 selection.

---

## Commands Run + Output

### Test suite (new tests)

```
pytest tests/test_benchmark_closure_operator.py -v --tb=short
```
Result: **17 passed** (0 failures after fixture fix: schema_version field required by `load_targets_manifest` for empty-targets test).

### Regression check (existing orchestrator tests)

```
pytest tests/test_close_benchmark_v1.py -v --tb=short
```
Result: **23 passed** (no regressions).

### Real smoke: `--export-tokens`

```
python -m polytool close-benchmark-v1 --export-tokens
```
Output:
```
[close-benchmark-v1] Exported 39 priority-1 token IDs
  source: config\benchmark_v1_gap_fill.targets.json
  txt:    config\benchmark_v1_priority1_tokens.txt
  json:   config\benchmark_v1_priority1_tokens.json
```
`wc -l config/benchmark_v1_priority1_tokens.txt` → 39 lines. Correct.

### Real smoke: `--status` (after export)

```
python -m polytool close-benchmark-v1 --status
```
Output:
```
========================================================================
  benchmark_v1 closure status  (2026-03-18T00:16:35Z)
========================================================================

  Manifest:             MISSING   config\benchmark_v1.tape_manifest
  Gap-fill targets:     FOUND    config\benchmark_v1_gap_fill.targets.json  (120 targets, 39 priority-1)
  Token export (.txt):  FOUND    config\benchmark_v1_priority1_tokens.txt  (39 tokens)
  Token export (.json): FOUND    config\benchmark_v1_priority1_tokens.json
  New-market targets:   MISSING   config\benchmark_v1_new_market_capture.targets.json
  Latest run:           2026-03-17  dry_run_smoke  [blocked, dry_run=True]

  Residual blockers (from config\benchmark_v1.gap_report.json):
    • bucket 'politics': shortage=9
    • bucket 'sports': shortage=11
    • bucket 'crypto': shortage=10
    • bucket 'near_resolution': shortage=9
    • bucket 'new_market': shortage=5

  Suggested next step:
    1. Start Docker:    docker compose up -d
    2. Fetch prices:    see docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md step 3
    3. Close Silver:    python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root <path> --jon-root <path>
========================================================================
```

Real-data smoke result: correct state reflected; 5 residual blockers from gap
report; suggested next step routes to Docker + Silver run.

---

## Runbook Summary

`docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md` provides 7 resumable steps:

| Step | Command | Done check |
|------|---------|-----------|
| 0 | Prerequisites | `ls data/raw/pmxt_archive/ \| head -3` |
| 1 | `docker compose up -d` | `curl http://localhost:8123/?query=SELECT+1` → 1 |
| 2 | `close-benchmark-v1 --export-tokens` | `wc -l config/benchmark_v1_priority1_tokens.txt` → 39 |
| 3 | `fetch-price-2min` loop over tokens.txt | CH price_2min COUNT > 0 |
| 4 | `close-benchmark-v1 --skip-new-market --pmxt-root ... --jon-root ...` | `--status` shows only new_market blocker |
| 5 | `close-benchmark-v1 --skip-silver` | `--status` shows Manifest: CREATED |
| 6 | `close-benchmark-v1 --pmxt-root ... --jon-root ...` | exit 0 |
| 7 | `benchmark-manifest --validate` | exit 0 |

---

## What Remains Before benchmark_v1 Is Real

1. **Docker up + Step 3**: fetch `price_2min` for the 39 priority-1 tokens in
   `config/benchmark_v1_priority1_tokens.txt`.
2. **Step 4 Silver run**: `close-benchmark-v1 --skip-new-market --pmxt-root
   data/raw/pmxt_archive --jon-root data/raw/jon_becker`
3. **Step 5 New-market**: requires live Polymarket listings <48h old + WS connectivity.
4. **Full closure**: once both Silver and new-market data are populated.

Exact commands in `docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md`.
