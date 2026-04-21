# 2026-04-08 GitHub Ingest Failure Debug

## Root Cause

- `github_ingest` was failing because the scheduler still targeted `https://github.com/Polymarket/polymarket-clob-client`.
- That repo now returns `HTTP 404 Not Found` from the GitHub API acquire path.
- The first configured repo (`py-clob-client`) still ran, but the second stale repo URL caused `research_acquire` to exit non-zero, which bubbled up as a generic `github_ingest` pipeline error.
- Health stayed RED until a newer successful `github_ingest` run replaced that stale error as the latest pipeline state.

## Files Changed And Why

- `packages/research/scheduling/scheduler.py`
  - Replaced the stale GitHub repo target with the live Polymarket CLOB repo URL: `https://github.com/Polymarket/clob-client`.

- `tests/test_ris_scheduler.py`
  - Added an offline regression test to lock the `github_ingest` job onto the current Polymarket repo URL set.

## Commands Run + Output

### Reproduce through the scheduler surface

```powershell
python -m polytool research-scheduler run-job github_ingest
```

Observed before fix:

```text
Running job: github_ingest (GitHub README ingestion)
Rejected | reason=Document body contains repeated URL (6x): https://clob.polymarket.com" | id=91caeb99d9517996
Error: fetch failed: HTTP 404 Not Found for https://api.github.com/repos/Polymarket/polymarket-clob-client
run_job: job 'github_ingest' failed: CLI job failed with exit_code=2.
Error: job 'github_ingest' failed (exit_code=1).
```

### Check health before fix

```powershell
python -m polytool research-health
```

Observed before fix:

```text
pipeline_failed RED Current pipeline issues: github_ingest failed (...) reddit_polymarket blocked (...)
```

### Verify the correct replacement repo path

```powershell
python -m polytool research-acquire --url https://github.com/Polymarket/clob-client --source-family github --no-eval --json
```

Observed:

```json
{
  "source_url": "https://github.com/Polymarket/clob-client",
  "source_family": "github",
  "normalized_title": "Typescript client for the Polymarket CLOB",
  "rejected": false,
  "reject_reason": null
}
```

### Regression tests

```powershell
pytest -q tests/test_ris_scheduler.py tests/test_ris_monitoring.py
```

Observed:

```text
94 passed in 0.92s
```

### Re-run the scheduler job after the fix

```powershell
python -m polytool research-scheduler run-job github_ingest
```

Observed after fix:

```text
Running job: github_ingest (GitHub README ingestion)
Rejected | reason=Document body contains repeated URL (6x): https://clob.polymarket.com" | id=91caeb99d9517996
Acquired: Typescript client for the Polymarket CLOB | family=github | source_id=2723fb3764bfe62e | doc_id=bf7e8fe6acf1... | chunks=1 | dedup=cached
Done.
```

### Re-run health after the fix

```powershell
python -m polytool research-health
```

Observed after fix:

```text
RIS Health Summary (48h window, 43 runs) — YELLOW
pipeline_failed YELLOW Current pipeline issues: reddit_polymarket blocked: Reddit live ingestion is not configured for `reddit_polymarket`: install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/.
```

## Test Results

- Direct `research-scheduler run-job github_ingest`: PASS after fix
- `research-health`: PASS, no longer RED because of `github_ingest`
- Targeted regression tests: PASS (`94 passed`)

## Final Behavior

Fixed

- `github_ingest` now succeeds end-to-end through the operator-facing scheduler surface.
- The stale GitHub repo URL no longer generates a generic pipeline failure.
- Health is now operator-meaningful: `github_ingest` is cleared, and the remaining `pipeline_failed` signal points only to the explicit Reddit setup block.

## Exact Operator Action Required

- For `github_ingest`: no action required after this fix.
- For overall RIS `pipeline_failed` to clear fully, complete the separate Reddit setup already surfaced in health:
  - install `praw` in the RIS runtime
  - set `REDDIT_CLIENT_ID`
  - set `REDDIT_CLIENT_SECRET`
  - set `REDDIT_USER_AGENT`
