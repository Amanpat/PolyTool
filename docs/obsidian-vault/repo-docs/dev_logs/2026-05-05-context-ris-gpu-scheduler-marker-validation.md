---
title: Context Ris Gpu Scheduler Marker Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Context - RIS GPU Scheduler Marker Validation

Date: 2026-05-05
Scope: Read-only mapping of how `ris-scheduler-gpu` receives and processes academic ingest jobs, and whether it is safe for Marker production validation without one-shot benchmark timeouts.
Status: CONTEXT COMPLETE - do not proceed with current scheduler validation as-is.

## Files inspected

- `docker-compose.yml`
- `Dockerfile.ris`
- `tools/cli/research_scheduler.py`
- `packages/research/scheduling/scheduler.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/extractors.py`
- `packages/research/ingestion/adapters.py`
- `packages/research/ingestion/pipeline.py`
- `packages/research/ingestion/source_cache.py`
- `packages/research/monitoring/run_log.py`
- `tools/cli/research_acquire.py`
- `tools/cli/research_parser_benchmark.py`
- `packages/polymarket/rag/knowledge_store.py`
- `tests/test_ris_scheduler.py`
- `docs/dev_logs/2026-05-05_ris-marker-short-paper-smoke.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`

## Answers

1. What command does `ris-scheduler-gpu` actually run?

   `docker-compose.yml` defines:

   ```yaml
   command: ["python", "-m", "polytool", "research-scheduler", "start"]
   environment:
     - RIS_PDF_PARSER=marker
   ```

   It uses `Dockerfile.ris`, mounts `./kb`, `./artifacts`, and `${USERPROFILE}/.cache/datalab:/home/polytool/.cache/datalab`, and depends on healthy ClickHouse.

2. Which jobs does it register?

   With the GPU service command, it registers all 8 scheduler jobs:

   - `academic_ingest`
   - `reddit_polymarket`
   - `reddit_others`
   - `blog_ingest`
   - `youtube_ingest`
   - `github_ingest`
   - `freshness_refresh`
   - `weekly_digest`

   The CPU service excludes only `academic_ingest`. The GPU service does not exclude the CPU-friendly jobs.

3. How does `academic_ingest` get triggered: schedule interval, queue/table, direct CLI, prefetch queue, or something else?

   It is APScheduler cron based, not queue/table based. The trigger is `hour="6,18"`: every day at 06:00 and 18:00 in the scheduler process timezone.

   It can also be triggered manually with:

   ```powershell
   python -m polytool research-scheduler run-job academic_ingest
   ```

   The job body is hardcoded. It calls `research_acquire.main()` twice:

   ```text
   --search "prediction markets microstructure" --source-family academic --no-eval
   --search "market microstructure liquidity" --source-family academic --no-eval
   ```

   `research-acquire --search` defaults to `--max-results 5`, so `academic_ingest` can process up to 10 papers per job run. The prefetch review queue exists inside `research-acquire` filter modes, but the scheduler does not poll it.

4. Can we submit one known arXiv ID to the scheduler without running the full schedule loop?

   No. Current `research-scheduler run-job` accepts only `job_id`; it has no `--url`, `--arxiv-id`, `--max-results`, or job-argument surface. `run-job academic_ingest` avoids the background loop, but still runs the two hardcoded topic searches rather than one known arXiv ID.

   Direct single-paper ingest exists:

   ```powershell
   python -m polytool research-acquire --url https://arxiv.org/abs/<ID> --source-family academic --no-eval
   ```

   That is not the scheduler job path.

5. Is there a timeout/cancel mechanism for long Marker parses?

   There is a per-paper wait timeout in `LiveAcademicFetcher`, default `_marker_timeout_seconds=300.0`. Marker extraction is run in a `ThreadPoolExecutor(max_workers=1)` and waited on with `future.result(timeout=...)`.

   On timeout, the code calls `_pool.shutdown(wait=False)`, sets `_MARKER_DISABLED`, and returns `body_source="marker_failed"` with a timeout failure reason. It does not kill the underlying Marker worker thread. The code comments explicitly state that true cancellation requires a process boundary and is deferred.

   Consequences:

   - At most one timed-out Marker worker should accumulate per process.
   - After the first timeout, Marker is disabled for that scheduler process until process restart.
   - This is not a hard cancel mechanism.
   - The current scheduler path is not safer than the benchmark path for very long parses; it just runs inside a long-lived process.

6. Where are scheduler logs written?

   There are three surfaces:

   - Container stdout/stderr: visible via `docker compose logs ris-scheduler-gpu` or `docker logs polytool-ris-scheduler-gpu`. There is no file logger configured in `research_scheduler.py` or `packages/research/scheduling/scheduler.py`.
   - Scheduler run log: `packages/research.monitoring.run_log.DEFAULT_RUN_LOG_PATH`, default `artifacts/research/run_log.jsonl`.
   - Underlying ingest artifacts: raw source cache under `artifacts/research/raw_source_cache/<family>/<source_id>.json`, acquisition reviews for direct URL mode under `artifacts/research/acquisition_reviews/acquisition_review.jsonl`, and accepted source-document metadata in `kb/rag/knowledge/knowledge.sqlite3`.

   Important caveat: `research-acquire --search` does not write per-run `run_log` records itself. The scheduler wrapper writes one `RunRecord` for the whole job.

7. Does the scheduler expose success/failure metadata such as `body_source=marker`, `marker_failed`, `body_length`, parse seconds?

   Not directly.

   The scheduler wrapper exposes only `job_id` and `exit_code` in `run-job --json`, and writes a coarse `RunRecord` with `pipeline`, `started_at`, `duration_s`, `accepted=0`, `rejected=0`, `errors=0`, and `exit_status`.

   Underlying fetch/ingest surfaces contain some metadata:

   - `body_source`, `body_length`, `failure_reason`, `fallback_reason`, `page_count`, `marker_version`, and structured metadata can be present in the raw source cache payload.
   - Accepted documents persist adapter metadata into `source_documents.metadata_json` in the SQLite knowledge store.
   - Rejected `marker_failed` papers are cached, but are rejected before source-document insert because the adapter sets body to empty and hard-stop length checks reject it.

   No production scheduler path records per-paper `parse_seconds`. `research-parser-benchmark` records `parse_seconds`, but that is the one-shot benchmark CLI, not the scheduler.

   Additional risk: `_job_run_academic_ingestion()` ignores return codes from `research_acquire.main()`. If `research-acquire` returns nonzero without raising, `run_job()` can still write `exit_status="ok"`.

8. Does running `ris-scheduler-gpu` require ClickHouse?

   At the Docker Compose level, yes. `ris-scheduler-gpu` has:

   ```yaml
   depends_on:
     clickhouse:
       condition: service_healthy
   ```

   The ClickHouse service requires `CLICKHOUSE_PASSWORD` in `.env` and must be healthy before the scheduler service starts.

   At the Python code path level, academic ingest uses local SQLite/JSONL/files (`KnowledgeStore`, raw-source cache, run log). The inspected scheduler and academic ingest code does not need ClickHouse directly.

9. Is there any risk it will start unrelated jobs/trading/n8n workflows?

   If started exactly as documented with a service name:

   ```powershell
   docker compose --profile ris-gpu up -d ris-scheduler-gpu
   ```

   Compose should start `ris-scheduler-gpu` and dependencies such as ClickHouse, not the `pair-bot` or `ris-n8n` profiled services.

   However, the GPU scheduler process itself registers all 8 RIS scheduler jobs, including reddit, blog, YouTube, GitHub, freshness, and weekly digest. If left running across schedule times, it can run unrelated research ingestion jobs.

   Do not run:

   ```powershell
   docker compose --profile ris-gpu up -d
   ```

   without the service name, because that can start all unprofiled services plus the active profile.

   Trading risk: `pair-bot-paper` and `pair-bot-live` are behind the `pair-bot` profile, so they are not started by the service-specific `ris-scheduler-gpu` command. n8n is behind `ris-n8n`, so it is not started by the service-specific GPU scheduler command.

10. What is the safest exact command sequence to validate one academic paper through the real scheduler path?

   No exact safe command sequence exists in the current codebase for "one known arXiv ID through the real scheduler path."

   Reasons:

   - Scheduler `run-job` cannot accept a URL/arXiv ID.
   - `academic_ingest` runs two hardcoded topic searches, not one known paper.
   - It may process up to 10 papers.
   - It has a default 300 second Marker wait timeout.
   - The timeout is not a hard cancel.
   - On timeout, the long-lived scheduler process disables future Marker attempts until restart.
   - Scheduler job success metadata is too coarse and may report `ok` even if inner acquisition returns nonzero.
   - The GPU service registers unrelated RIS jobs unless explicitly changed.

## Exact safe validation command sequence

Current safe introspection only, already safe because it does not start Docker, Marker, or APScheduler:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m polytool research-scheduler status --json
python -m polytool research-scheduler start --dry-run
python -m polytool research-scheduler start --dry-run --exclude-jobs academic_ingest
```

Current single-paper direct ingest path, not scheduler validation:

```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-acquire `
    --url https://arxiv.org/abs/2604.24366 `
    --source-family academic `
    --no-eval `
    --json
```

Do not treat that as scheduler-mode validation. It is direct CLI ingest inside the GPU image.

Tempting current scheduler path, not recommended for validation:

```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-scheduler run-job academic_ingest --json
```

Do not use this for the one-paper Marker validation objective. It runs two searches, can process up to 10 papers, uses the current non-hard timeout behavior, and does not expose per-paper Marker success metadata.

Minimum safe command sequence after adding a missing control surface would look like this:

```powershell
docker compose --profile ris-gpu up -d clickhouse

docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-scheduler run-academic-url `
    --url https://arxiv.org/abs/2604.24366 `
    --no-eval `
    --json `
    --marker-timeout 1800 `
    --run-log artifacts/research/run_log.jsonl

docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-health --run-log artifacts/research/run_log.jsonl
```

That command does not exist today. It documents the missing shape: a scheduler-owned one-paper trigger with an explicit Marker timeout and JSON output that includes parser metadata.

## Risks and blockers

- Current GPU scheduler registers unrelated RIS jobs. It needs an academic-only mode or compose command override if used as a long-running validation service.
- There is no single-paper scheduler submit path.
- There is no queue/table that the scheduler monitors for one-off academic ingest jobs.
- Marker timeout is thread-based and does not cancel the underlying worker.
- A timeout disables Marker for the whole scheduler process until restart.
- Scheduler `run_job()` logs `accepted=0`, `rejected=0`, `errors=0` regardless of underlying per-paper outcomes.
- `academic_ingest` ignores `research_acquire.main()` return codes.
- Scheduler logs do not expose `body_source`, `body_length`, `marker_failed`, or parse seconds directly.
- `docs/dev_logs/2026-05-05_ris-marker-short-paper-smoke.md` says scheduler mode has "No per-paper timeout"; current code contradicts that. The production fetcher default is 300 seconds per paper.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` expects GPU parsing of a typical arXiv paper in <=10 seconds. The 2026-05-05 smoke log shows 1200-1800 second timeouts on math-heavy papers, so the packet assumptions need revision or narrower paper selection.

## Recommendation

Add the missing control surface first, then validate. Do not proceed with current `ris-scheduler-gpu` scheduler validation as-is.

Recommended minimum changes for a future work unit:

1. Add a scheduler-owned one-paper academic trigger, either `research-scheduler run-academic-url --url ...` or `run-job academic_ingest --url ...`.
2. Make that path pass through the same production `LiveAcademicFetcher` and `IngestPipeline`.
3. Add explicit parser metadata to JSON output and/or run log: `body_source`, `body_length`, `failure_reason`, `marker_failed`, `parse_seconds`, `doc_id`, `chunk_count`, `rejected`, `reject_reason`.
4. Propagate nonzero `research_acquire.main()` return codes into scheduler job failure.
5. Add an academic-only scheduler mode or `--include-jobs academic_ingest`/compose command so GPU scheduler does not register unrelated RIS jobs for validation.
6. Consider a process boundary for Marker extraction if the objective is "safe without zombie timeout contamination."

## Commands run

```powershell
git status --short
```

Output:

```text
 M .claude/scheduled_tasks.lock
 M .dockerignore
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Pre-fetch_SVM_Topic_Filter_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M tools/cli/research_parser_benchmark.py
?? docs/dev_logs/2026-05-03_codex-rereview-ris-marker-production-rollout.md
?? docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md
?? docs/dev_logs/2026-05-04_codex-review-docker-storage-optimization.md
?? docs/dev_logs/2026-05-04_docker-storage-optimization-fixes.md
?? docs/dev_logs/2026-05-04_docker-storage-optimization.md
?? docs/runbooks/docker_storage.md
```

```powershell
git log --oneline -5
```

Output:

```text
38a13c2 docs(ris): short-paper Marker smoke validation - systematic timeout diagnosis
103eeb3 fix(ris): site-packages/static EPERM fix + L1 benchmark timeout diagnosis
3348aef fix(ris): L1 Marker rollout - Codex FAIL resolution (adapter rejection, scheduler split, cache mount)
94a074c feat(ris): L1 Marker production rollout - default parser, GPU Docker, explicit failure semantics
f5bf5af L3.1 Complete
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m polytool --help
```

Output: exited 0 and listed `research-scheduler`, `research-acquire`, and `research-parser-benchmark` under RIS commands.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m polytool research-scheduler status --json
```

Output:

```json
[
  {
    "id": "academic_ingest",
    "name": "ArXiv academic ingestion",
    "trigger_description": "every 12h at 06:00 and 18:00",
    "callable_name": "_job_run_academic_ingestion"
  },
  {
    "id": "reddit_polymarket",
    "name": "r/polymarket ingestion",
    "trigger_description": "every 6h at 00:00, 06:00, 12:00, 18:00",
    "callable_name": "_job_run_reddit_polymarket"
  },
  {
    "id": "reddit_others",
    "name": "Other subreddits ingestion",
    "trigger_description": "daily at 03:00",
    "callable_name": "_job_run_reddit_others"
  },
  {
    "id": "blog_ingest",
    "name": "Blog/RSS ingestion",
    "trigger_description": "every 4h at 02:00, 06:00, 10:00, 14:00, 18:00, 22:00",
    "callable_name": "_job_run_blog_ingestion"
  },
  {
    "id": "youtube_ingest",
    "name": "YouTube transcript ingestion",
    "trigger_description": "Mondays at 04:00",
    "callable_name": "_job_run_youtube_ingestion"
  },
  {
    "id": "github_ingest",
    "name": "GitHub README ingestion",
    "trigger_description": "Wednesdays at 04:00",
    "callable_name": "_job_run_github_ingestion"
  },
  {
    "id": "freshness_refresh",
    "name": "Freshness tier recalculation",
    "trigger_description": "Sundays at 02:00",
    "callable_name": "_job_run_freshness_refresh"
  },
  {
    "id": "weekly_digest",
    "name": "Weekly research digest",
    "trigger_description": "Sundays at 08:00",
    "callable_name": "_job_run_weekly_digest"
  }
]
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m polytool research-scheduler start --dry-run
```

Output:

```text
RIS Scheduler -- Dry-run mode (no scheduler started)
Registered jobs (8):
  academic_ingest        every 12h at 06:00 and 18:00
  reddit_polymarket      every 6h at 00:00, 06:00, 12:00, 18:00
  reddit_others          daily at 03:00
  blog_ingest            every 4h at 02:00, 06:00, 10:00, 14:00, 18:00, 22:00
  youtube_ingest         Mondays at 04:00
  github_ingest          Wednesdays at 04:00
  freshness_refresh      Sundays at 02:00
  weekly_digest          Sundays at 08:00

Note: Twitter/X ingestion is not scheduled (fetcher not yet implemented).
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m polytool research-scheduler start --dry-run --exclude-jobs academic_ingest
```

Output:

```text
RIS Scheduler -- Dry-run mode (no scheduler started)
Registered jobs (7):
  reddit_polymarket      every 6h at 00:00, 06:00, 12:00, 18:00
  reddit_others          daily at 03:00
  blog_ingest            every 4h at 02:00, 06:00, 10:00, 14:00, 18:00, 22:00
  youtube_ingest         Mondays at 04:00
  github_ingest          Wednesdays at 04:00
  freshness_refresh      Sundays at 02:00
  weekly_digest          Sundays at 08:00
Excluded jobs: academic_ingest

Note: Twitter/X ingestion is not scheduled (fetcher not yet implemented).
```

Other commands were read-only file inspection through `Get-Content`, `Get-ChildItem`, and `Select-String`. `rg` was attempted first but failed with `Access is denied`, so PowerShell-native inspection was used instead.

No Docker commands were run. Marker was not run. The scheduler was not started. No code files were edited.

## Codex review summary

Tier: Skip. Read-only context mapping plus this dev log only; no code review requested and no code changes made.
