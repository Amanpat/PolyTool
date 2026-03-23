# Benchmark Closure After Full-Target Prefetch

## Files changed and why

- `artifacts/benchmark_closure/2026-03-20/bf64af3f-17bc-429f-ac09-8fbf05ad66ad/benchmark_closure_run_v1.json`
  - New closure artifact from the fixed real-shell `close-benchmark-v1 --skip-new-market` run.
- `config/benchmark_v1.gap_report.json`
  - Refreshed by the orchestrator's benchmark refresh at the end of Stage 2.
- `docs/CURRENT_STATE.md`
  - Updated repo truth with the latest fixed closure-run outcome and remaining shortages.
- `docs/dev_logs/2026-03-20_benchmark_closure_after_full_target_prefetch.md`
  - This run log.

## Context

- Branch remained `phase-1`.
- Repo root: `D:\Coding Projects\Polymarket\PolyTool`
- Raw roots used:
  - `D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive`
  - `D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker`
- The only prior blocker was `CLICKHOUSE_PASSWORD` missing in the active shell.
- This run set `CLICKHOUSE_PASSWORD=admin` in the same real PowerShell session used for Docker, the closure command, and the status check.

## Commands run

```powershell
git branch --show-current
```

Output:

```text
phase-1
```

```powershell
$c=Get-Content config/benchmark_v1.gap_report.json; $c[0..([Math]::Min($c.Length-1,240))]
```

Key output before the resumed run:

```text
generated_at: 2026-03-20T21:22:37+00:00
inventory_by_tier: gold=12, silver=38
shortages_by_bucket: politics=9, sports=11, crypto=10, near_resolution=0, new_market=5
bucket_summary.near_resolution.candidate_count=21
```

```powershell
$env:CLICKHOUSE_PASSWORD = "admin"
if ([string]::IsNullOrWhiteSpace($env:CLICKHOUSE_PASSWORD)) { "__CLICKHOUSE_PASSWORD_MISSING__" } else { "__CLICKHOUSE_PASSWORD_PRESENT__ length=$($env:CLICKHOUSE_PASSWORD.Length)" }
docker compose up -d
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

Key output:

```text
__CLICKHOUSE_PASSWORD_PRESENT__ length=5
Container polytool-clickhouse        Running
Container polytool-api               Running
Container polytool-grafana           Running
Container polytool-clickhouse        Healthy
Container polytool-migrate           Started
[fetch-price-2min] prefetching price_2min for 118 unique token IDs (120 targets)
Total: 450327 rows fetched, 450327 inserted, 0 skipped
[close-benchmark-v1] Stage 4: Finalization
  final_status: blocked
  [BLOCKER] bucket 'politics': shortage=9
  [BLOCKER] bucket 'sports': shortage=11
  [BLOCKER] bucket 'crypto': shortage=10
  [BLOCKER] bucket 'new_market': shortage=5
[close-benchmark-v1] run artifact: artifacts\benchmark_closure\2026-03-20\bf64af3f-17bc-429f-ac09-8fbf05ad66ad\benchmark_closure_run_v1.json
[benchmark-manifest] blocked: wrote gap report config\benchmark_v1.gap_report.json
[benchmark-manifest] shortages: politics=9, sports=11, crypto=10, new_market=5
```

```powershell
python -m polytool close-benchmark-v1 --status
```

Key output:

```text
Latest run: 2026-03-20  bf64af3f-17bc-429f-ac09-8fbf05ad66ad  [blocked, dry_run=False]
Residual blockers:
  bucket 'politics': shortage=9
  bucket 'sports': shortage=11
  bucket 'crypto': shortage=10
  bucket 'new_market': shortage=5
```

## Artifact paths

- Closure artifact:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-20\bf64af3f-17bc-429f-ac09-8fbf05ad66ad\benchmark_closure_run_v1.json`
- Refreshed gap report:
  `D:\Coding Projects\Polymarket\PolyTool\config\benchmark_v1.gap_report.json`

## Before / After shortages

- Before (`config/benchmark_v1.gap_report.json` generated `2026-03-20T21:22:37+00:00`)
  - `politics=9`
  - `sports=11`
  - `crypto=10`
  - `near_resolution=0`
  - `new_market=5`
  - `inventory_by_tier`: `gold=12`, `silver=38`
  - `bucket_summary.near_resolution.candidate_count=21`
- After (`config/benchmark_v1.gap_report.json` generated `2026-03-21T00:20:14+00:00`)
  - `politics=9`
  - `sports=11`
  - `crypto=10`
  - `near_resolution=0`
  - `new_market=5`
  - `inventory_by_tier`: `gold=12`, `silver=118`
  - `bucket_summary.near_resolution.candidate_count=81`

## Final result

- `run_id`: `bf64af3f-17bc-429f-ac09-8fbf05ad66ad`
- `final_status`: `blocked`
- Stage 2 did use the fixed full-target prefetch path:
  - `targets_count=120`
  - `fetch_price_2min.token_count=118`
  - `fetch_price_2min.priority1_count=39`
  - `tapes_created=120`
  - `benchmark_refresh.outcome=gap_report_updated`
- The refreshed shortages are still:
  - `politics=9`
  - `sports=11`
  - `crypto=10`
  - `near_resolution=0`
  - `new_market=5`
- `benchmark_v1` is **not** reduced to `new_market` only.
- The prefetch fix increased Silver inventory materially, but the remaining blocker is now downstream of `price_2min` availability.

## Exact next manual command

Do not start new-market capture yet; the benchmark is not `new_market`-only.

```powershell
python -m polytool close-benchmark-v1 --status
```
