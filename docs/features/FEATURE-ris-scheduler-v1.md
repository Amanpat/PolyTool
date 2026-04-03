# FEATURE: RIS Scheduler v1 (APScheduler Background Ingestion)

**Quick task:** quick-260403-1s3
**Date:** 2026-04-03
**Status:** Shipped

---

## What It Is

The RIS Scheduler v1 provides an APScheduler-backed background ingestion loop for the
Research Intelligence System (RIS). It registers 8 named periodic jobs that call existing
RIS CLI main() functions on a cron-like schedule, enabling fully automated, unattended
ingestion of academic papers, social media content, blogs, YouTube transcripts, and GitHub
READMEs.

---

## Registered Jobs

| ID | Name | Schedule | Source Family |
|----|------|----------|---------------|
| `academic_ingest` | ArXiv academic ingestion | every 12h (06:00, 18:00) | academic |
| `reddit_polymarket` | r/polymarket ingestion | every 6h (00:00, 06:00, 12:00, 18:00) | reddit |
| `reddit_others` | Other subreddits ingestion | daily at 03:00 | reddit |
| `blog_ingest` | Blog/RSS ingestion | every 4h (02:00, 06:00, 10:00, 14:00, 18:00, 22:00) | blog |
| `youtube_ingest` | YouTube transcript ingestion | Mondays at 04:00 | youtube |
| `github_ingest` | GitHub README ingestion | Wednesdays at 04:00 | github |
| `freshness_refresh` | Freshness tier recalculation | Sundays at 02:00 | academic |
| `weekly_digest` | Weekly research digest | Sundays at 08:00 | (digest) |

**Twitter/X: explicitly deferred.** No live fetcher exists yet (see RIS_02 social ingestion
spec). Twitter/X ingestion is NOT registered in the scheduler.

---

## CLI Usage

```bash
# List all registered jobs (no APScheduler required)
python -m polytool research-scheduler status

# List jobs as JSON
python -m polytool research-scheduler status --json

# Start the background scheduler (blocking; Ctrl-C to stop)
python -m polytool research-scheduler start

# Dry-run: show registered jobs, then exit without starting
python -m polytool research-scheduler start --dry-run

# Run a single job immediately
python -m polytool research-scheduler run-job academic_ingest
python -m polytool research-scheduler run-job weekly_digest --json
```

---

## Installation

APScheduler is an optional dependency in the `[ris]` group:

```bash
pip install 'polytool[ris]'
# or directly:
pip install 'apscheduler>=3.10.0,<4.0'
```

The `JOB_REGISTRY` and all job callables are importable without APScheduler installed.
APScheduler is only required when `start_research_scheduler()` is called without a
`_scheduler_factory` override.

---

## How to Extend

To add a new job:

1. Add a new callable to `packages/research/scheduling/scheduler.py`:
   ```python
   def _job_run_my_new_source() -> None:
       import tools.cli.research_acquire as research_acquire
       research_acquire.main(["--url", "https://...", "--source-family", "blog", "--no-eval"])
   ```

2. Register it in `_JOB_FN_MAP`:
   ```python
   "_job_run_my_new_source": _job_run_my_new_source,
   ```

3. Add an entry to `JOB_REGISTRY`:
   ```python
   {
       "id": "my_new_source",
       "name": "My new source ingestion",
       "trigger_description": "daily at 07:00",
       "callable_name": "_job_run_my_new_source",
   },
   ```

4. Add the trigger to `_triggers` inside `start_research_scheduler()`:
   ```python
   "my_new_source": {"hour": 7},
   ```

---

## Architecture

```
polytool/__main__.py
  └── tools/cli/research_scheduler.py    [CLI: status | start | run-job]
         └── packages/research/scheduling/scheduler.py
                ├── JOB_REGISTRY          [8 job descriptors]
                ├── _JOB_FN_MAP           [id -> callable]
                ├── start_research_scheduler(_scheduler_factory, _job_runner)
                └── run_job(job_id) -> int
                       └── tools/cli/research_acquire.main() [academic, reddit, blog, youtube, github]
                       └── tools/cli/research_report.main()  [digest]
```

**Injectable hooks** (`_scheduler_factory`, `_job_runner`) allow full offline testing
without APScheduler installed. Tests use a `_FakeScheduler` and capture job_id calls
without making any network requests.

---

## Files

- `packages/research/scheduling/__init__.py` — package marker with re-exports
- `packages/research/scheduling/scheduler.py` — core scheduler module
- `tools/cli/research_scheduler.py` — CLI entrypoint
- `tests/test_ris_scheduler.py` — 28 offline unit tests
