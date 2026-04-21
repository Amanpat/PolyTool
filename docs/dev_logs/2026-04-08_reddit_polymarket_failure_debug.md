# 2026-04-08 Reddit Polymarket Failure Debug

## Root Cause

Primary runtime root cause on 2026-04-08:

- `reddit_polymarket` was running without live Reddit setup in `polytool-ris-scheduler`.
- `praw` was not installed in the runtime.
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT` were unset.

Truthfulness bugs found while tracing the path:

1. Scheduler job wrappers called CLI `main()` functions but ignored non-zero return codes.
   - Result: a failed live fetch could print an error but still be recorded as scheduler success.
2. Health check `pipeline_failed` scanned historical errors in-window instead of the latest state per pipeline.
   - Result: stale old Reddit failures kept producing misleading RED output even after a newer rerun.

Additional observed path mismatch:

- Scheduler wiring uses a subreddit URL (`https://www.reddit.com/r/polymarket/`).
- `LiveRedditFetcher.fetch()` is still shaped like a single-submission fetcher.
- That is a separate latent live-path issue once Reddit setup is present; it did not block the operator-facing missing-setup fix delivered here.

## Files Changed And Why

- `packages/research/scheduling/scheduler.py`
  - Propagate non-zero CLI results instead of silently treating them as success.
  - Add explicit Reddit setup preflight for `reddit_polymarket` and `reddit_others`.
  - Record blocked/missing-setup runs as `exit_status="partial"` with operator metadata.
  - Preserve exception text in run-log metadata for unexpected failures.

- `packages/research/monitoring/health_checks.py`
  - Evaluate the latest run per pipeline instead of any stale error in the window.
  - Surface operator-blocked partial states as explicit messages.
  - Include both real failures and blocked/setup states in the health message.

- `tests/test_ris_scheduler.py`
  - Added regression coverage for non-zero CLI propagation.
  - Added regression coverage for Reddit missing-setup partial outcome.
  - Added regression coverage for partial run-log records.

- `tests/test_ris_monitoring.py`
  - Added regression coverage for operator-blocked partial health status.
  - Added regression coverage so stale older errors do not dominate newer pipeline state.
  - Added regression coverage for mixed real-failure + blocked-state health messaging.

## Commands Run + Output

### Runtime tracing

```powershell
python -m polytool research-health
```

Observed before fix:

- `pipeline_failed` reported `reddit_polymarket` failed at `2026-04-08T18:00:24+00:00`.

```powershell
docker exec polytool-ris-scheduler python -m polytool research-acquire --url https://www.reddit.com/r/polymarket/ --source-family reddit --no-eval
```

Observed:

```text
Error: fetch failed: praw is required for live Reddit fetching -- install praw or use fetch_raw() with a fixture dict.
```

```powershell
docker exec polytool-ris-scheduler python -c "import importlib.util, os; print('praw_installed=', importlib.util.find_spec('praw') is not None); print('REDDIT_CLIENT_ID=', bool(os.getenv('REDDIT_CLIENT_ID'))); print('REDDIT_CLIENT_SECRET=', bool(os.getenv('REDDIT_CLIENT_SECRET'))); print('REDDIT_USER_AGENT=', bool(os.getenv('REDDIT_USER_AGENT')))"
```

Observed:

```text
praw_installed= False
REDDIT_CLIENT_ID= False
REDDIT_CLIENT_SECRET= False
REDDIT_USER_AGENT= False
```

### Test verification

```powershell
pytest -q tests/test_ris_scheduler.py tests/test_ris_monitoring.py tests/test_ris_research_acquire_cli.py
```

Observed:

```text
107 passed in 1.36s
```

### Runtime refresh

```powershell
docker compose build ris-scheduler
docker compose up -d --force-recreate ris-scheduler
```

Observed:

- `polytool-ris-scheduler` rebuilt and recreated successfully.

### Post-fix direct scheduler path

```powershell
docker exec polytool-ris-scheduler python -m polytool research-scheduler run-job reddit_polymarket
```

Observed after fix:

```text
Running job: reddit_polymarket (r/polymarket ingestion)
Done.
SKIPPED: Reddit live ingestion is not configured for `reddit_polymarket`: install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/
run_job: job 'reddit_polymarket' partial: Reddit live ingestion is not configured for `reddit_polymarket`: install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/
```

### Post-fix stored run-log record

```powershell
docker exec polytool-ris-scheduler python -c "from packages.research.scheduling.scheduler import run_job; from pathlib import Path; run_job('reddit_polymarket'); p=Path('artifacts/research/run_log.jsonl'); print(p.read_text(encoding='utf-8').splitlines()[-1])"
```

Observed:

```json
{"accepted":0,"duration_s":0.01617158599947288,"errors":0,"exit_status":"partial","metadata":{"job_id":"reddit_polymarket","missing_dependencies":["praw"],"missing_env_vars":["REDDIT_CLIENT_ID","REDDIT_CLIENT_SECRET","REDDIT_USER_AGENT"],"operator_action":"install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT","operator_message":"Reddit live ingestion is not configured for `reddit_polymarket`: install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/","operator_status":"missing_setup","source_family":"reddit","source_url":"https://www.reddit.com/r/polymarket/"},"pipeline":"reddit_polymarket","rejected":0,"run_id":"4a5c81d7faa9","schema_version":"run_log_v1","started_at":"2026-04-08T19:01:35+00:00"}
```

### Post-fix health output

```powershell
docker exec polytool-ris-scheduler python -m polytool research-health
```

Observed:

```text
pipeline_failed RED Current pipeline issues: github_ingest failed (...) reddit_polymarket blocked: Reddit live ingestion is not configured for `reddit_polymarket`: install `praw` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/.
```

Key point:

- `reddit_polymarket` is no longer a generic unexplained failure.
- It is now explicitly labeled as blocked on missing Reddit setup.
- Overall summary stays RED because there is still an unrelated current `github_ingest` failure in the same 48h health window.

## Test Results

- Targeted unit tests: PASS
- Direct `reddit_polymarket` scheduler path in live container: PASS for graceful blocked-state behavior
- `research-health` rerun in live container: PASS for explicit operator-facing Reddit status

## Final Behavior

Expected-missing-setup

- When Reddit live setup is absent, `reddit_polymarket` no longer depends on a generic `pipeline_failed` message to explain itself.
- The run log now records a `partial` state with explicit operator metadata.
- Health now reports the current Reddit state as blocked/missing setup instead of an opaque scheduler failure.
- Real failures are still visible and still keep health RED when they are genuinely unresolved.

## Exact Operator Action Required

To enable live Reddit ingestion in `polytool-ris-scheduler`:

1. Install `praw` in the RIS runtime/image.
2. Set these environment variables for the scheduler container:
   - `REDDIT_CLIENT_ID`
   - `REDDIT_CLIENT_SECRET`
   - `REDDIT_USER_AGENT`
3. Rebuild/recreate `ris-scheduler`.

Note:

- After setup is present, the live scheduler URL still targets a subreddit URL and should be re-verified because the current `LiveRedditFetcher.fetch()` implementation is still shaped like a single-submission fetch path.
