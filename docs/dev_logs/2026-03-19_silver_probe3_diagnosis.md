# Dev Log: Silver Probe3 Diagnosis

**Date:** 2026-03-19
**Branch:** `phase-1`
**Objective:** Run a constrained 3-target Silver diagnostic probe for the
remaining non-new-market buckets and classify the exact outcome for
politics / sports / crypto.

---

## Outcome

The 3-target Silver probe executed successfully and wrote a real
`gap_fill_run.json`.

- Run dir:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329`
- `targets_attempted=3`
- `tapes_created=3`
- `failure_count=0`
- `skip_count=0`
- `metadata_summary.clickhouse=3`
- `stdout.txt` contains the expected live summary
- `stderr.txt` is empty

There were no hard per-target failures. All three targets landed in the same
degraded success class: low-confidence Silver tapes built entirely from
`price_2min_guide` events because no pmxt anchor snapshot and no Jon-Becker
fills were found for the requested windows.

---

## Files Changed And Why

- `docs/CURRENT_STATE.md`
  Updated repo truth. The file previously said Mode 2 live generation had not
  been run; it now records the real 3-target probe result and the actual next
  benchmark step.
- `docs/dev_logs/2026-03-19_silver_probe3_diagnosis.md`
  Recorded this execution, artifact paths, per-target outcomes, and the next
  manual command.
- `artifacts/silver/manual_gap_fill_probe3_20260319_190329/targets_manifest.json`
  Ad hoc probe manifest for this diagnostic run.

Generated artifacts from the run:

- `artifacts/silver/manual_gap_fill_probe3_20260319_190329/gap_fill_run.json`
- `artifacts/silver/manual_gap_fill_probe3_20260319_190329/stdout.txt`
- `artifacts/silver/manual_gap_fill_probe3_20260319_190329/stderr.txt`
- `artifacts/silver/7440104415081523/2026-03-15T10-00-09Z/silver_meta.json`
- `artifacts/silver/7440104415081523/2026-03-15T10-00-09Z/silver_events.jsonl`
- `artifacts/silver/6468399453420164/2026-03-15T10-00-15Z/silver_meta.json`
- `artifacts/silver/6468399453420164/2026-03-15T10-00-15Z/silver_events.jsonl`
- `artifacts/silver/1130052343087492/2026-03-15T10-00-48Z/silver_meta.json`
- `artifacts/silver/1130052343087492/2026-03-15T10-00-48Z/silver_events.jsonl`

No source code, tests, specs, runbooks, or branches were changed.

---

## Probe Manifest Used

```json
{
  "schema_version": "benchmark_gap_fill_v1",
  "targets": [
    {
      "bucket": "politics",
      "priority": 1,
      "slug": "100-tariff-on-canada-in-effect-by-june-30",
      "token_id": "74401044150815233212315835920011636780189603928313623397904798907525089171384",
      "window_start": "2026-03-15T10:00:09.554000+00:00",
      "window_end": "2026-03-15T14:59:42.056000+00:00"
    },
    {
      "bucket": "sports",
      "priority": 1,
      "slug": "2025-2026-epl-winner-more-than-90-points",
      "token_id": "64683994534201646450394391725616228695952599577525859664835161186648784031970",
      "window_start": "2026-03-15T10:00:15.373000+00:00",
      "window_end": "2026-03-15T14:59:20.801000+00:00"
    },
    {
      "bucket": "crypto",
      "priority": 1,
      "slug": "another-crypto-hack-over-100m-before-2027",
      "token_id": "113005234308749261641273809104525222871932092818248517014310727082878210014694",
      "window_start": "2026-03-15T10:00:48.018000+00:00",
      "window_end": "2026-03-15T14:57:01.370000+00:00"
    }
  ]
}
```

---

## Commands Run + Output

1. Confirm branch and check shell secret presence

```powershell
git branch --show-current
if ([string]::IsNullOrWhiteSpace($env:CLICKHOUSE_PASSWORD)) { 'MISSING' } else { 'PRESENT' }
```

Observed output before resume:

- Branch: `phase-1`
- Password check: `MISSING`

The operator then supplied a non-empty `CLICKHOUSE_PASSWORD` in the active
Windows shell and the probe resumed.

2. Start local services

```powershell
docker compose up -d
```

Observed output:

- `polytool-clickhouse`, `polytool-simtrader-studio`, `polytool-api`,
  `polytool-grafana` were already running
- `polytool-clickhouse` reported healthy
- `polytool-migrate` started

3. First batch attempt with an invalid ad hoc manifest shape

```powershell
python -m polytool batch-reconstruct-silver --targets-manifest "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\targets_manifest.json" --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker" --clickhouse-password "$env:CLICKHOUSE_PASSWORD" --out "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\batch_manifest.json" --gap-fill-out "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\gap_fill_run.json"
```

Observed output in `stderr.txt`:

```text
Error: --targets-manifest: targets manifest root must be a JSON object
```

The probe manifest was then rewritten to the required
`benchmark_gap_fill_v1` object shape and re-run.

4. Successful live probe run

```powershell
python -m polytool batch-reconstruct-silver --targets-manifest "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\targets_manifest.json" --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker" --clickhouse-password "$env:CLICKHOUSE_PASSWORD" --out "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\batch_manifest.json" --gap-fill-out "D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\gap_fill_run.json"
```

Observed output in `stdout.txt`:

```text
[batch-reconstruct-silver] [LIVE] targets-manifest mode
  manifest: D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\targets_manifest.json  targets=3
  out-root: artifacts
  batch_run_id: be6018cf-05f0-492a-a2d7-732f8f29ac7f

[batch-reconstruct-silver] gap-fill complete
  targets_attempted: 3
  tapes_created: 3
  failure_count: 0
  skip_count: 0
  metadata: ch=3 jsonl=0 skipped=0
  [OK] 7440104415081523... bucket=politics confidence=low events=28
  [OK] 6468399453420164... bucket=sports confidence=low events=29
  [OK] 1130052343087492... bucket=crypto confidence=low events=28

  gap-fill result: D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\gap_fill_run.json
```

Observed output in `stderr.txt` after the successful run:

```text
[empty]
```

---

## Per-Target Outcomes

- `politics`
  slug: `100-tariff-on-canada-in-effect-by-june-30`
  status: `success`
  class: low-confidence, price_2min-only Silver tape
  event_count: `28`
  fill_count: `0`
  price_2min_count: `28`
  warnings: `pmxt_anchor_missing`, `jon_fills_missing`
  artifacts:
  `artifacts/silver/7440104415081523/2026-03-15T10-00-09Z/silver_meta.json`
  `artifacts/silver/7440104415081523/2026-03-15T10-00-09Z/silver_events.jsonl`

- `sports`
  slug: `2025-2026-epl-winner-more-than-90-points`
  status: `success`
  class: low-confidence, price_2min-only Silver tape
  event_count: `29`
  fill_count: `0`
  price_2min_count: `29`
  warnings: `pmxt_anchor_missing`, `jon_fills_missing`
  artifacts:
  `artifacts/silver/6468399453420164/2026-03-15T10-00-15Z/silver_meta.json`
  `artifacts/silver/6468399453420164/2026-03-15T10-00-15Z/silver_events.jsonl`

- `crypto`
  slug: `another-crypto-hack-over-100m-before-2027`
  status: `success`
  class: low-confidence, price_2min-only Silver tape
  event_count: `28`
  fill_count: `0`
  price_2min_count: `28`
  warnings: `pmxt_anchor_missing`, `jon_fills_missing`
  artifacts:
  `artifacts/silver/1130052343087492/2026-03-15T10-00-48Z/silver_meta.json`
  `artifacts/silver/1130052343087492/2026-03-15T10-00-48Z/silver_events.jsonl`

Event-file inspection confirmed the dominant event type for all three tapes:

- politics: `price_2min_guide x28`
- sports: `price_2min_guide x29`
- crypto: `price_2min_guide x28`

---

## Dominant Shared Failure / Warning Class

There was no shared hard failure.

The dominant shared class is:

```text
SUCCESS, but degraded to low-confidence price_2min-only output because:
  1. pmxt_anchor_missing
  2. jon_fills_missing
```

Exact implication:

- Silver tape writing works for the sampled politics / sports / crypto targets
- ClickHouse metadata writes also work
- The remaining non-new-market benchmark risk is not a hard execution failure
  in these three sampled buckets
- The unresolved benchmark question is whether the same result holds across the
  full gap-fill manifest, especially `near_resolution`

---

## Artifact Paths

- Run dir:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329`
- Gap-fill result:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\gap_fill_run.json`
- Stdout:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\stdout.txt`
- Stderr:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\manual_gap_fill_probe3_20260319_190329\stderr.txt`

Per-target Silver outputs:

- politics:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\7440104415081523\2026-03-15T10-00-09Z\silver_meta.json`
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\7440104415081523\2026-03-15T10-00-09Z\silver_events.jsonl`
- sports:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\6468399453420164\2026-03-15T10-00-15Z\silver_meta.json`
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\6468399453420164\2026-03-15T10-00-15Z\silver_events.jsonl`
- crypto:
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\1130052343087492\2026-03-15T10-00-48Z\silver_meta.json`
  `D:\Coding Projects\Polymarket\PolyTool\artifacts\silver\1130052343087492\2026-03-15T10-00-48Z\silver_events.jsonl`

---

## Final Result

- Real `gap_fill_run.json` created: **Yes**
- politics outcome: **success, low-confidence, price_2min-only**
- sports outcome: **success, low-confidence, price_2min-only**
- crypto outcome: **success, low-confidence, price_2min-only**
- Dominant hard failure class across sampled non-new-market buckets: **none**
- Dominant shared degraded class: **pmxt anchor missing + Jon fills missing**
- `benchmark_v1` reduced to `new_market` only: **not proven yet**

Exact next manual command:

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'; python -m polytool batch-reconstruct-silver --targets-manifest "config/benchmark_v1_gap_fill.targets.json" --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker" --clickhouse-password "$env:CLICKHOUSE_PASSWORD" --benchmark-refresh --gap-fill-out "artifacts/silver/manual_gap_fill_full_$ts/gap_fill_run.json"
```
