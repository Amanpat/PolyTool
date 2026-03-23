# Silver Gap-Fill Full Run

## Files changed and why

- `artifacts/silver/manual_gap_fill_full_20260319_213841/`
  - Full direct Silver gap-fill run artifacts.
  - Includes `gap_fill_run.json`, `stdout.txt`, `stderr.txt`, `exit_code.txt`, and the local launcher used to let the batch finish past the 1-hour tool ceiling.
- `config/benchmark_v1.gap_report.json`
  - Refreshed by `--benchmark-refresh` after the completed direct batch.
- `docs/CURRENT_STATE.md`
  - Updated repo truth to reflect the completed full-manifest run and the remaining benchmark shortages.
- `docs/dev_logs/2026-03-20_silver_gap_fill_full_run.md`
  - This run log.

## Context

- Branch stayed on `phase-1`.
- Repo root: `D:\Coding Projects\Polymarket\PolyTool`
- `CLICKHOUSE_PASSWORD` was present in-shell before the completed run.
- Docker services were brought up locally before the batch.

## Commands run

```powershell
git branch --show-current
```

Output:

```text
phase-1
```

```powershell
docker compose up -d
```

Key output:

```text
Container polytool-clickhouse  Running
Container polytool-api         Running
Container polytool-grafana     Running
Container polytool-clickhouse  Healthy
Container polytool-migrate     Started
```

Initial direct foreground attempts used the requested command shape but hit the Codex tool's 1-hour ceiling before a final artifact could be written. The completed pass used the same underlying batch command via a launcher in the final run directory:

```powershell
python -m polytool batch-reconstruct-silver `
  --targets-manifest config/benchmark_v1_gap_fill.targets.json `
  --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" `
  --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker" `
  --clickhouse-password "$env:CLICKHOUSE_PASSWORD" `
  --benchmark-refresh `
  --gap-fill-out "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\gap_fill_run.json" `
  1> "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\stdout.txt" `
  2> "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\stderr.txt"
```

Completed launcher invocation:

```powershell
cmd.exe /d /c 'start "gapfill-full-20260319-213841" /b cmd.exe /d /c call "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\launch_full_gap_fill.cmd"'
```

Post-run summary command:

```powershell
python -m polytool summarize-gap-fill --path artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json --json
```

## Artifact paths

- Run dir: `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841`
- Gap-fill artifact: `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\gap_fill_run.json`
- Stdout: `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\stdout.txt`
- Stderr: `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\stderr.txt`
- Refreshed gap report: `D:\Coding Projects\Polymarket\PolyTool\config\benchmark_v1.gap_report.json`

## Command output summary

`stdout.txt` ended with:

```text
[batch-reconstruct-silver] gap-fill complete
  targets_attempted: 120
  tapes_created: 120
  failure_count: 0
  skip_count: 0
  metadata: ch=120 jsonl=0 skipped=0
  gap-fill result: D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_full_20260319_213841\gap_fill_run.json
```

`stderr.txt` ended with:

```text
[benchmark-manifest] blocked: wrote gap report config\benchmark_v1.gap_report.json
[benchmark-manifest] shortages: politics=9, sports=11, crypto=10, new_market=5
```

`exit_code.txt`:

```text
0
```

## Summary counts

- `targets_attempted`: 120
- `tapes_created`: 120
- `failure_count`: 0
- `skip_count`: 0
- Metadata writes: `clickhouse=120`, `jsonl_fallback=0`, `skipped=0`
- Success classes:
  - `confidence=low, price_2min_only`: 40
  - `confidence=none, empty_tape`: 80
- Warning classes:
  - `pmxt_anchor_missing`: 120
  - `jon_fills_missing`: 120
  - `price_2min_missing`: 80

## Bucket-by-bucket outcome

- `politics`: 30 successes, 0 failures, 0 skips; 10 `low`, 20 `none`; 10 eventful tapes, 20 zero-event tapes
- `sports`: 30 successes, 0 failures, 0 skips; 11 `low`, 19 `none`; 11 eventful tapes, 19 zero-event tapes
- `crypto`: 30 successes, 0 failures, 0 skips; 10 `low`, 20 `none`; 10 eventful tapes, 20 zero-event tapes
- `near_resolution`: 30 successes, 0 failures, 0 skips; 9 `low`, 21 `none`; 9 eventful tapes, 21 zero-event tapes

Nuance:

- The run reports `tapes_created=120`, but only 118 unique `out_dir` paths were written because two slugs appeared in more than one bucket list:
  - `claudia-sheinbaum-out-as-president-of-mexico-by-june-30-791` in `politics` and `sports`
  - `brian-armstrong-out-as-coinbase-ceo-before-2027` in `sports` and `crypto`

## Refreshed benchmark shortages

From `config/benchmark_v1.gap_report.json` generated at `2026-03-20T21:22:37+00:00`:

- `politics`: 9
- `sports`: 11
- `crypto`: 10
- `near_resolution`: 0
- `new_market`: 5

Additional refreshed inventory summary:

- `inventory_by_tier`: `gold=12`, `silver=38`
- `selected_by_tier`: `gold=6`, `silver=9`
- `manifest_exists`: `false`

## Final result

- The full direct Silver gap-fill run completed successfully and wrote a real `gap_fill_run.json`.
- `benchmark_v1` is **not** reduced to `new_market` only.
- Remaining non-new-market shortages are still:
  - `politics=9`
  - `sports=11`
  - `crypto=10`
- `near_resolution` is now closed (`0` shortage).

## Exact next manual command

```powershell
python -m polytool summarize-gap-fill --path artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json --json
```
