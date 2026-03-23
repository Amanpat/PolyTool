# Phase 1 Finalization Check

## Files changed and why

- `docs/CURRENT_STATE.md`
  - Updated repo truth to record the finalization check result: the benchmark
    closed once `benchmark-manifest` scanned `artifacts/tapes/new_market`.
- `docs/dev_logs/2026-03-21_phase1_finalization_check.md`
  - Created the required execution log for the finalization check, including
    commands, tape inspection results, manifest outcome, validation outcome,
    and the next manual command.

## Context

- Branch required: `phase-1`
- Repo root: `D:\Coding Projects\Polymarket\PolyTool`
- Starting known benchmark state:
  - `politics=0`
  - `sports=0`
  - `crypto=0`
  - `near_resolution=0`
  - `new_market=5`
- User-supplied target tape dirs:
  - `sol-updown-5m-1774209300`
  - `xrp-updown-5m-1774209300`
  - `bnb-updown-5m-1774209300`
  - `hype-updown-5m-1774209300`
  - `eth-updown-5m-1774209300`
- Hanging sixth from the prior run:
  - `doge-updown-5m-1774209300`

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

Output at check start included existing unrelated dirty-tree entries; no source,
test, spec, runbook, or branch changes were made by this check.

```powershell
$p = Get-Process -Id 9660 -ErrorAction SilentlyContinue; if($p){ Stop-Process -Id 9660; Start-Sleep -Seconds 2; if(Get-Process -Id 9660 -ErrorAction SilentlyContinue){ 'PID9660_STILL_ALIVE' } else { 'PID9660_STOPPED' } } else { 'PID9660_ALREADY_GONE' }
```

Output:

```text
PID9660_STOPPED
```

### Tape-dir inspection

Checked for:
- `raw_ws.jsonl`
- `events.jsonl`
- `meta.json`
- `watch_meta.json`

```text
sol-updown-5m-1774209300   raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
xrp-updown-5m-1774209300   raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
bnb-updown-5m-1774209300   raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
hype-updown-5m-1774209300  raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
eth-updown-5m-1774209300   raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
doge-updown-5m-1774209300  raw_ws/events/meta/watch_meta: PRESENT/PRESENT/PRESENT/PRESENT
```

Additional tape dir found under `artifacts/tapes/new_market/`:

```text
btc-updown-5m-1774209300   raw_ws/events/meta/watch_meta: PRESENT/PRESENT/MISSING/PRESENT
```

```powershell
python -m polytool benchmark-manifest
```

Output:

```text
[benchmark-manifest] blocked: wrote gap report config\benchmark_v1.gap_report.json
[benchmark-manifest] shortages: new_market=5
```

Read-only proof from the refreshed gap report:

```text
inventory_roots = ["artifacts/simtrader/tapes", "artifacts/silver"]
bucket_summary.new_market.candidate_count = 0
bucket_summary.new_market.selected_count = 0
bucket_summary.new_market.shortage = 5
```

```powershell
python -m polytool close-benchmark-v1 --status
```

Output:

```text
Manifest: MISSING
Residual blockers: bucket 'new_market': shortage=5
```

### Cheapest completion attempt using the tapes already on disk

`benchmark-manifest --help` showed a repeatable `--root DIR` flag. The
benchmark was then rerun with the new-market tape root included:

```powershell
python -m polytool benchmark-manifest --root artifacts/simtrader/tapes --root artifacts/silver --root artifacts/tapes/new_market
```

Output:

```text
[benchmark-manifest] manifest written: config\benchmark_v1.tape_manifest (50 paths)
[benchmark-manifest] audit written: config\benchmark_v1.audit.json
[benchmark-manifest] lock written: config\benchmark_v1.lock.json
```

```powershell
python -m polytool close-benchmark-v1 --status
```

Output:

```text
Manifest: CREATED   config\benchmark_v1.tape_manifest
*** benchmark_v1 is CLOSED - config/benchmark_v1.tape_manifest exists ***
Suggested next step:
  Nothing - benchmark is closed. Proceed to Gate 2 scenario sweep.
```

```powershell
python -m polytool benchmark-manifest validate --manifest config/benchmark_v1.tape_manifest
```

Output:

```text
[benchmark-manifest] valid: config\benchmark_v1.tape_manifest
[benchmark-manifest] bucket counts: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
[benchmark-manifest] manifest sha256: d27369a22c526b5824fc127b0f4c9ebdab8db1544a234f49535d317921633827
[benchmark-manifest] lock verified: config\benchmark_v1.lock.json
```

## Whether the five tapes were sufficient

Yes, the already-recorded new-market tape inventory on disk was sufficient to
close the benchmark without another live capture, but only after
`benchmark-manifest` was pointed at the correct root.

Important detail:
- The user-listed five tape dirs were not the exact five chosen for the final
  manifest.
- `config/benchmark_v1.audit.json` selected these five `new_market` tapes:
  - `xrp-updown-5m-1774209300`
  - `sol-updown-5m-1774209300`
  - `btc-updown-5m-1774209300`
  - `bnb-updown-5m-1774209300`
  - `hype-updown-5m-1774209300`
- `eth-updown-5m-1774209300` and `doge-updown-5m-1774209300` were discovered
  but were not needed for the final quota of 5.

## Manifest and validation result

- `config/benchmark_v1.tape_manifest`: created
- `config/benchmark_v1.lock.json`: created
- `config/benchmark_v1.audit.json`: created
- Validation: passed
- Final benchmark status: closed

## Final result

Phase 1 is complete. The cheapest completion path was not another live capture;
it was rerunning `benchmark-manifest` with `artifacts/tapes/new_market` added
to the inventory roots.

## Exact blocker before the fix

Before the explicit-root rerun, the exact blocker was:

```text
default benchmark-manifest inventory_roots excluded artifacts/tapes/new_market, so the recorded new-market Gold tapes were not discovered and new_market remained shortage=5
```

## Exact next manual command

```powershell
python -m polytool close-benchmark-v1 --status
```
