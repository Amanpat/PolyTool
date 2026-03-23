# Phase 1 Final New-Market Execution Retry

## Files changed and why

- `docs/CURRENT_STATE.md`
  - Updated repo truth to record the corrected-flag retry outcome on
    2026-03-21: dry-run passed, live capture started and recorded real tapes,
    but the process continued beyond the required `new_market=5` quota and did
    not emit a result artifact or benchmark refresh.
- `docs/dev_logs/2026-03-21_phase1_final_new_market_execution_retry.md`
  - Created the required retry execution log with commands, outputs, artifact
    paths, final result, and the exact next manual command.

## Context

- Branch required: `phase-1`
- Repo root: `D:\Coding Projects\Polymarket\PolyTool`
- Starting benchmark state supplied for this retry:
  - `politics=0`
  - `sports=0`
  - `crypto=0`
  - `near_resolution=0`
  - `new_market=5`
- Scope rule followed:
  - touched only `docs/CURRENT_STATE.md` and this retry dev log
- Stop rule followed:
  - stop on the first real live blocker after the corrected command

## Commands run

```powershell
git branch --show-current
```

Output:

```text
phase-1
```

```powershell
git status --short
```

Output at retry start included existing unrelated dirty-tree entries; no source,
test, spec, or runbook files were edited by this retry.

```powershell
Get-Location
```

Output:

```text
Path
----
D:\Coding Projects\Polymarket\PolyTool
```

```powershell
$env:CLICKHOUSE_PASSWORD='admin'; if ([string]::IsNullOrWhiteSpace($env:CLICKHOUSE_PASSWORD)) { 'CLICKHOUSE_PASSWORD_MISSING' } else { 'CLICKHOUSE_PASSWORD_PRESENT length=' + $env:CLICKHOUSE_PASSWORD.Length }
```

Output:

```text
CLICKHOUSE_PASSWORD_PRESENT length=5
```

```powershell
if (Test-Path 'config/benchmark_v1_new_market_capture.targets.json') { 'TARGETS_PRESENT' } else { 'TARGETS_MISSING' }
```

Output:

```text
TARGETS_PRESENT
```

```powershell
docker compose up -d
```

Key output:

```text
Container polytool-clickhouse  Running
Container polytool-simtrader-studio  Running
Container polytool-api  Running
Container polytool-grafana  Running
Container polytool-clickhouse  Healthy
Container polytool-migrate  Started
```

```powershell
$env:CLICKHOUSE_PASSWORD='admin'; python -m polytool capture-new-market-tapes --targets-manifest config/benchmark_v1_new_market_capture.targets.json --out-root artifacts/tapes/new_market --dry-run
```

Output summary:

```text
[capture-new-market-tapes] [DRY-RUN] targets=300
  manifest: config\benchmark_v1_new_market_capture.targets.json
  out-root: artifacts\tapes\new_market
  batch_run_id: 5ee5c4ff-0f9b-4282-a4bb-3e4584287b72

[capture-new-market-tapes] complete
  targets_attempted: 300
  tapes_created:     231
  failure_count:     0
  skip_count:        69
  metadata: ch=0 jsonl=0 skipped=231
```

Representative skip reason from dry-run:

```text
[SKIP] fr2-gre-clf-2026-04-03-total-4pt5  reason=resolve_slug failed for 'fr2-gre-clf-2026-04-03-total-4pt5': cannot identify YES/NO from outcomes ['Over', 'Under'] ...
```

```powershell
$env:CLICKHOUSE_PASSWORD='admin'; python -m polytool capture-new-market-tapes --targets-manifest config/benchmark_v1_new_market_capture.targets.json --out-root artifacts/tapes/new_market --benchmark-refresh
```

Observed execution result:

```text
The shell command timed out after 2 hours in the tool window, but the Python
process continued running in the background as PID 9660. Read-only checks
confirmed that live tape directories were being written under
artifacts/tapes/new_market/.
```

## Stop point

- The corrected dry-run passed.
- The corrected live capture started and recorded real tapes.
- Exact live blocker:
  - after satisfying the required `new_market=5` quota, the live capture did
    not terminate into `capture_run_*.json` / benchmark refresh; instead it
    kept running and began a sixth tape (`doge-updown-5m-1774209300`).
- Because the live command never reached its result phase:
  - `python -m polytool close-benchmark-v1 --status` was not run
  - `python -m polytool benchmark-manifest validate --manifest config/benchmark_v1.tape_manifest` was not run

## Read-only post-stop checks

These checks were used only to record exact state after the live blocker.

### Live process

```text
ProcessName : python
Id          : 9660
StartTime   : 3/21/2026 4:41:30 PM
CPU         : 4.984375
Responding  : True
CommandLine : "...python.exe\" -m polytool capture-new-market-tapes --targets-manifest config/benchmark_v1_new_market_capture.targets.json --out-root artifacts/tapes/new_market --benchmark-refresh
```

### New-market tape directories on disk

```text
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\sol-updown-5m-1774209300
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\xrp-updown-5m-1774209300
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\bnb-updown-5m-1774209300
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\hype-updown-5m-1774209300
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\eth-updown-5m-1774209300
D:\Coding Projects\Polymarket\PolyTool\artifacts\tapes\new_market\doge-updown-5m-1774209300
```

### Sixth tape still active

```text
artifacts\tapes\new_market\doge-updown-5m-1774209300\raw_ws.jsonl    EXISTS  2026-03-21T19:36:26-04:00  865145
artifacts\tapes\new_market\doge-updown-5m-1774209300\events.jsonl    EXISTS  2026-03-21T19:11:54-04:00  3772
artifacts\tapes\new_market\doge-updown-5m-1774209300\meta.json       MISSING
artifacts\tapes\new_market\doge-updown-5m-1774209300\watch_meta.json EXISTS  2026-03-21T19:11:54-04:00  469
```

### Result/manifest state

```text
config/benchmark_v1.tape_manifest    MISSING
config/benchmark_v1.lock.json        MISSING
config/benchmark_v1.gap_report.json  EXISTS  2026-03-21T16:15:15-04:00  179725
Newest capture_run artifact remains:
  artifacts/simtrader/tapes/new_market_capture/capture_run_558b6d88.json
```

## Artifact paths

- Targets manifest:
  - `config/benchmark_v1_new_market_capture.targets.json`
- Live tape root:
  - `artifacts/tapes/new_market/`
- Six tape directories written before stop:
  - `artifacts/tapes/new_market/sol-updown-5m-1774209300`
  - `artifacts/tapes/new_market/xrp-updown-5m-1774209300`
  - `artifacts/tapes/new_market/bnb-updown-5m-1774209300`
  - `artifacts/tapes/new_market/hype-updown-5m-1774209300`
  - `artifacts/tapes/new_market/eth-updown-5m-1774209300`
  - `artifacts/tapes/new_market/doge-updown-5m-1774209300`
- Newest existing capture run artifact:
  - `artifacts/simtrader/tapes/new_market_capture/capture_run_558b6d88.json`
- Manifest:
  - `config/benchmark_v1.tape_manifest` (missing)
- Lock file:
  - `config/benchmark_v1.lock.json` (missing)
- Current gap report on disk:
  - `config/benchmark_v1.gap_report.json`

## Results

- Dry-run result:
  - passed
  - `targets_attempted=300`
  - `tapes_created=231`
  - `failure_count=0`
  - `skip_count=69`
- Live capture result:
  - started and recorded real tapes, but did not finish
  - live process PID `9660` continued beyond the required five-tape quota
  - no new `capture_run_*.json`
  - no benchmark refresh result
- Manifest validation result:
  - not run
- Phase 1 complete:
  - no
- Exact blocker:
  - corrected live capture continued past the required `new_market=5` quota and
    kept recording a sixth tape instead of terminating into result writing and
    benchmark refresh

## Final result

Phase 1 is not complete. The corrected CLI flags solved the dry-run blocker and
the live path is able to record Gold tapes, but the live execution did not stop
after five new-market tapes and therefore never reached `capture_run_*.json`,
benchmark refresh, manifest creation, or validation.

## Exact next manual command

```powershell
Stop-Process -Id 9660
```
