# Codex Rereview - RIS Marker Production Rollout

Date: 2026-05-03
Reviewer: Codex
Scope: Re-review Claude's fixes for the prior L1 Marker production rollout Codex FAIL blockers.

## Verdict

PASS

The prior P0/P1 blockers are confirmed fixed. Docker GPU validation may proceed.
This rereview did not run live GPU benchmarks, install model weights, or run live
Marker parsing.

## Repo State

Startup checks:

```text
git status --short
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
```

These Obsidian vault changes were pre-existing and unrelated to this review. I did
not touch them.

```text
git log --oneline -5
3348aef fix(ris): L1 Marker rollout - Codex FAIL resolution (adapter rejection, scheduler split, cache mount)
94a074c feat(ris): L1 Marker production rollout - default parser, GPU Docker, explicit failure semantics
f5bf5af L3.1 Complete
ac3aebc feat(ris): L3.1 prefetch review queue + label store + hold-review mode
a923e6a Academic Pipeline Improvements L0 - L2
```

`python -m polytool --help`: exit 0. CLI loaded and listed `research-acquire`
and `research-scheduler`.

## Commands Run

```text
git diff --name-status HEAD~1..HEAD
M       Dockerfile.ris
M       docker-compose.yml
M       docs/CURRENT_DEVELOPMENT.md
M       docs/INDEX.md
A       docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
A       docs/dev_logs/2026-05-03_codex-review-ris-marker-production-rollout.md
A       docs/dev_logs/2026-05-03_ris-marker-production-rollout-validation.md
M       docs/features/ris-marker-structural-parser-scaffold.md
M       docs/obsidian-vault/Claude Desktop/Current-Focus.md
M       packages/research/ingestion/adapters.py
M       packages/research/ingestion/fetchers.py
M       packages/research/scheduling/scheduler.py
M       tests/test_ris_academic_pdf.py
A       tests/test_ris_scheduler_split.py
M       tools/cli/research_scheduler.py
```

```text
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_research_acquire_cli.py
71 passed in 1.13s
```

```text
python -m pytest tests/test_ris_scheduler*.py
ERROR: file or directory not found: tests/test_ris_scheduler*.py
no tests ran in 0.00s
```

PowerShell did not expand the pytest glob, so I reran the present file explicitly:

```text
python -m pytest tests/test_ris_scheduler_split.py
5 passed in 0.12s
```

```text
python -m polytool research-acquire --help
exit 0; help printed successfully.
```

```text
python -m polytool research-scheduler --help
exit 0; help printed successfully.
```

Additional scheduler CLI check:

```text
python -m polytool research-scheduler start --help
usage: polytool research-scheduler start [-h] [--dry-run]
                                         [--exclude-jobs JOB_ID [JOB_ID ...]]
```

CPU scheduler dry-run with the compose flag:

```text
python -m polytool research-scheduler start --dry-run --exclude-jobs academic_ingest
Registered jobs (7):
  reddit_polymarket
  reddit_others
  blog_ingest
  youtube_ingest
  github_ingest
  freshness_refresh
  weekly_digest
Excluded jobs: academic_ingest
```

GPU/default scheduler dry-run:

```text
python -m polytool research-scheduler start --dry-run
Registered jobs (8):
  academic_ingest
  reddit_polymarket
  reddit_others
  blog_ingest
  youtube_ingest
  github_ingest
  freshness_refresh
  weekly_digest
```

```text
docker compose config | Out-Null
exit 0
```

Full `docker compose config` output was intentionally not copied because Compose
can expand `.env` values. Non-secret targeted checks:

```text
docker compose --profile ris-gpu config --services
clickhouse
api
grafana
migrate
ris-scheduler
ris-scheduler-gpu
```

```text
docker compose --profile ris-gpu config | Select-String ...
ris-scheduler:
  command includes: --exclude-jobs academic_ingest
  RIS_PDF_PARSER: pdfplumber
ris-scheduler-gpu:
  driver: nvidia
  capabilities: [gpu]
  RIS_PDF_PARSER: marker
  target: /home/polytool/.cache/datalab
```

```text
git diff --check
exit 0; only LF/CRLF warnings for the pre-existing Obsidian working-tree files.
No whitespace errors were reported.
```

```text
git ls-files | Select-String -Pattern model/cache/weight extensions
exit 0; no matches.

git ls-files -o --exclude-standard | Select-String -Pattern model/cache/weight extensions
exit 0; no matches.
```

Direct adapter probe:

```text
python -c "... AcademicAdapter marker_failed probe ..."
body_len 0
body_source marker_failed
failure_reason encrypted PDF
abstract_len 200
```

## Prior Blocker Status

### 1. `marker_failed` could still ingest abstract via AcademicAdapter fallback

Status: FIXED.

`packages/research/ingestion/adapters.py` now checks `body_source ==
"marker_failed"` before the normal `body_text or abstract` fallback and sets
`body = ""`. It also propagates `failure_reason` metadata. The direct adapter
probe and the new `TestAcademicAdapterMarkerFailedRejection` tests confirm that
a long abstract is preserved only as metadata and does not become `doc.body`.

`packages/research/ingestion/fetchers.py` also preserves this behavior in both
`fetch()` and `search_by_topic()`: when `body_source` is `marker_failed`,
`body_text` remains `""` instead of falling back to the abstract.

### 2. CPU `ris-scheduler` still ran `academic_ingest` with `RIS_PDF_PARSER=pdfplumber`

Status: FIXED.

`start_research_scheduler()` now accepts `exclude_job_ids`, the CLI exposes
`research-scheduler start --exclude-jobs`, and `docker-compose.yml` starts the
CPU `ris-scheduler` with `--exclude-jobs academic_ingest`. The dry-run with that
flag registers 7 jobs and excludes `academic_ingest`.

### 3. GPU service mounted Marker cache under `/root` while runtime user is `polytool`

Status: FIXED.

`Dockerfile.ris` runs as `USER polytool`, and the Compose GPU service now mounts
the host datalab cache to `/home/polytool/.cache/datalab`. The profile config
render confirms the target path.

## Verification Criteria

1. `marker_failed` cannot become abstract-only body downstream: PASS.
2. CPU scheduler excludes `academic_ingest` in Docker Compose: PASS.
3. GPU scheduler is the only service intended to run `academic_ingest`: PASS.
4. Marker cache volume points to the runtime-user cache path: PASS.
5. No model weights/caches/artifacts are committed: PASS.
6. No L2/SVM/L4/n8n/trading scope creep in production code: PASS.

Note: the GPU scheduler command still starts the full scheduler registry. That
means the GPU service would also register non-academic jobs if run as a long-lived
service. This is not a blocker for the prior P0/P1 fixes or Docker GPU validation,
because the CPU service no longer runs `academic_ingest`; however, an `--include-jobs
academic_ingest` style mode would make the service split cleaner before unattended
production operation.

## Docker GPU Validation

May proceed.

Allowed next checks are the Docker GPU build, `nvidia-smi` smoke inside the GPU
service, Marker import, live arXiv parse, and warm 3-paper Marker benchmark. They
were not run in this rereview because the instructions explicitly said not to run
the live GPU benchmark or install model weights.

## Remaining Fixes

No remaining fixes block Docker GPU validation.

Recommended follow-up before unattended production scheduling: add an include-only
scheduler option for `ris-scheduler-gpu` so that profile service registers only
`academic_ingest`, avoiding duplicated non-academic jobs when the CPU and GPU
schedulers run together.
