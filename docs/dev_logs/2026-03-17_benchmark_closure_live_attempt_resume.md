# Dev Log: Benchmark Closure Live Attempt Resume

**Date:** 2026-03-17
**Branch:** `phase-1`
**Objective:** Resume the real `benchmark_v1` closure live attempt from the
blocked `fetch-price-2min` step after the Windows stdout fix, and stop on the
next real blocker with evidence saved under `artifacts/benchmark_closure/`.

---

## Outcome

`benchmark_v1` closure did **not** complete.

- `config/benchmark_v1.tape_manifest` was **not** created.
- The original `fetch-price-2min` stdout blocker is cleared.
- The next real blocker is downstream in the Silver closure / refresh path.
- Execution stopped before `new-market-capture`, `capture-new-market-tapes`,
  and final closure because the resumed Silver closure remained blocked.

Artifact root for this resumed attempt:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\live_attempt_resume_2026-03-17_210038`

Silver closure run artifact written by the orchestrator:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\084f807b-789e-4cb1-9833-6536c3da822a\benchmark_closure_run_v1.json`

---

## Status Before Resume

Baseline read-only command:

```powershell
python -m polytool close-benchmark-v1 --status
```

Key output:

- Manifest: `MISSING   config\benchmark_v1.tape_manifest`
- Gap-fill targets: `FOUND` (`120` targets, `39` priority-1)
- Token export `.txt`: `FOUND` (`39` tokens)
- Token export `.json`: `FOUND`
- New-market targets: `FOUND     config\benchmark_v1_new_market_capture.targets.json`
- Branch check: `phase-1`

Raw proof:

- `01_close_benchmark_status_pre.txt`
- `03_docker_ps_escalated.stdout.txt`
- `04_clickhouse_select1.stdout.txt`

---

## Commands Run

The following commands were executed for the resumed attempt.

```powershell
git branch --show-current
git status --short
python -m polytool close-benchmark-v1 --status
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
docker exec polytool-clickhouse clickhouse-client --user polytool_admin --password <from .env> --query "SELECT 1"
python -m polytool fetch-price-2min --token-file config/benchmark_v1_priority1_tokens.txt --clickhouse-host localhost --clickhouse-user polytool_admin --clickhouse-password <from .env>
python -m polytool close-benchmark-v1 --status
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
python -m polytool close-benchmark-v1 --status
Test-Path config\benchmark_v1.tape_manifest
```

Notes:

- The first `--skip-new-market` run was launched inside the sandbox and is not
  treated as the repo blocker. Its stderr shows sandbox socket denial to
  `https://clob.polymarket.com/prices-history` (`WinError 10013`), so the same
  command was rerun outside the sandbox.
- No source code, tests, specs, runbooks, or branches were changed.

---

## Key Outputs

### Docker / ClickHouse readiness

- `docker ps` showed `polytool-clickhouse` as `Up ... (healthy)`.
- `docker exec polytool-clickhouse ... "SELECT 1"` returned `1`.

Proof:

- `03_docker_ps_escalated.stdout.txt`
- `04_clickhouse_select1.stdout.txt`

### Resumed live fetch

Command:

```powershell
python -m polytool fetch-price-2min --token-file config/benchmark_v1_priority1_tokens.txt --clickhouse-host localhost --clickhouse-user polytool_admin --clickhouse-password <from .env>
```

Observed stdout:

```text
fetch-price-2min [LIVE]: 38 token(s) -> polytool.price_2min
...
Total: 149626 rows fetched, 149626 inserted, 0 skipped
```

Important detail:

- The token file has 39 lines, but one token ID is duplicated, so the live
  fetch processed 38 unique tokens.

Proof:

- `05_fetch_price_2min.stdout.txt`
- `06_close_benchmark_status_post_fetch.stdout.txt`

### Silver closure result

Escalated command:

```powershell
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

Observed stdout:

- `silver_gap_fill.status`: `completed`
- `fetch_price_2min.status`: `success`
- `batch_reconstruct.failure_count`: `0`
- `benchmark_refresh.outcome`: `gap_report_updated`
- Final status: `blocked`
- Residual blockers remained:
  - `bucket 'politics': shortage=9`
  - `bucket 'sports': shortage=11`
  - `bucket 'crypto': shortage=10`
  - `bucket 'near_resolution': shortage=9`
  - `bucket 'new_market': shortage=5`

Proof:

- `11_close_benchmark_skip_new_market_escalated.stdout.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\084f807b-789e-4cb1-9833-6536c3da822a\benchmark_closure_run_v1.json`

---

## Exact Blocker After The Fix

The next real blocker is **not** `fetch-price-2min`. The live fetch succeeded.
The blocker is the Silver closure / benchmark refresh path after the fetch.

Exact evidence from escalated Silver stderr:

- repeated `price_2min: ClickHouse query failed: 400 Client Error: Bad Request for url: http://localhost:8123/?query=SELECT...`
- repeated `jon: missing required columns. token_col=None ts_col=timestamp in [...]`
- final line:
  `[benchmark-manifest] blocked: wrote gap report config\benchmark_v1.gap_report.json`

Why this is the blocker:

- `close-benchmark-v1 --skip-new-market` exited nonzero after stage completion.
- `benchmark_refresh.return_code` is `2`.
- `manifest_written` is `false`.
- `config/benchmark_v1.tape_manifest` still does not exist.
- Because the Silver / refresh path is still blocked, execution did not proceed
  to new-market capture or final closure.

Tight proof paths:

- blocker stderr:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\live_attempt_resume_2026-03-17_210038\11_close_benchmark_skip_new_market_escalated.stderr.txt`
- blocker stdout:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\live_attempt_resume_2026-03-17_210038\11_close_benchmark_skip_new_market_escalated.stdout.txt`
- orchestrator run artifact:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\084f807b-789e-4cb1-9833-6536c3da822a\benchmark_closure_run_v1.json`

---

## Status After Stop

Read-only status after the escalated Silver closure:

```powershell
python -m polytool close-benchmark-v1 --status
Test-Path config\benchmark_v1.tape_manifest
```

Key results:

- Status still reports `Manifest: MISSING   config\benchmark_v1.tape_manifest`
- `Test-Path config\benchmark_v1.tape_manifest` returned `False`

Proof:

- `12_close_benchmark_status_after_silver.stdout.txt`
- `13_manifest_exists_after_silver.txt`

---

## Raw Log Index

- `01_close_benchmark_status_pre.txt`
- `02_docker_ps.stderr.txt`
- `03_docker_ps_escalated.stdout.txt`
- `03_docker_ps_escalated.stderr.txt`
- `04_clickhouse_select1.stdout.txt`
- `04_clickhouse_select1.stderr.txt`
- `05_fetch_price_2min.stdout.txt`
- `05_fetch_price_2min.stderr.txt`
- `06_close_benchmark_status_post_fetch.stdout.txt`
- `06_close_benchmark_status_post_fetch.stderr.txt`
- `07_close_benchmark_skip_new_market.stdout.txt`
- `07_close_benchmark_skip_new_market.stderr.txt`
- `08_close_benchmark_status_after_timeout.stdout.txt`
- `08_close_benchmark_status_after_timeout.stderr.txt`
- `09_stuck_sandbox_process.txt` (attempted capture; access denied)
- `10_python_processes_after_stop.txt`
- `11_close_benchmark_skip_new_market_escalated.stdout.txt`
- `11_close_benchmark_skip_new_market_escalated.stderr.txt`
- `12_close_benchmark_status_after_silver.stdout.txt`
- `12_close_benchmark_status_after_silver.stderr.txt`
- `13_manifest_exists_after_silver.txt`

---

## Summary

- Benchmark complete: **No**
- Manifest created: **No**
- Exact blocker: Silver closure / benchmark refresh remains blocked after the
  successful live fetch, with repeated `price_2min` ClickHouse `400` query
  failures and `jon` missing-column errors
- Raw log directory:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\live_attempt_resume_2026-03-17_210038`
