---
title: Codex Verify Marker Ipc Live Validation Fixes
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker IPC Live-Validation Fixes

Date: 2026-05-07
Type: read-only verification review
Scope: review-only. This dev log is the only file created by Codex in this pass.
Verdict: FAIL

## Objective

Verify the Marker IPC live-validation blocker fixes and rerun plan, then decide
whether a second live Docker validation may be attempted next.

## Decision

FAIL. A second live Docker validation may NOT be attempted next from the current
rerun plan as written.

The code fixes are materially in place: the Dockerfile stub gap is patched,
the IPC timeout path restarts the worker without setting `_MARKER_DISABLED`,
pdfplumber fallback was not added to the IPC path, queue v0 semantics remain
covered, and targeted tests pass.

The blocker is the rerun plan. It is not executable/safe as written:

1. `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md`
   uses invalid enqueue commands at lines 108, 173, and 200. The CLI requires
   `enqueue --url URL_OR_ID`; the plan omits `--url`.
2. The plan marks rerun readiness prerequisites as checked at lines 352-356
   even though the same plan says the Docker image was not rebuilt, the queue
   reset still must happen, and papers 2-3 still need verification.
3. The candidate set is not ready: `2604.24366` is a good simple anchor, but
   `2204.05149` is explicitly unknown and `2412.14173` is explicitly risky
   with one attempt left. The plan recommends replacing `2412.14173` but does
   not provide a concrete queue-safe replacement/exclusion path before the
   `--max-items 3` Docker run.

## Verification Checklist

| Check | Result | Notes |
|---|---|---|
| 1. Stale current L1-unblocked claims gone or marked historical/fixed | PASS | `git grep` only found stale-labeled historical references. |
| 2. L1 remains blocked pending Feature 3 gates | PASS | Current docs and work packet state L1 remains blocked until >=3 warm papers with papers 2+ <=10s. |
| 3. Dockerfile.ris rebuild gap fixed | PASS | `packages/research/relevance_filter` stub dir added to `Dockerfile.ris`. Build was not run. |
| 4. Worker restart-after-timeout implemented and tested | PASS | `_marker_ipc_worker_extract()` calls `restart()` on `marker_timeout`; tests cover restart behavior. |
| 5. IPC failures do not set `_MARKER_DISABLED` | PASS | IPC path has no `_MARKER_DISABLED.set()`; tests assert it remains clear. |
| 6. No pdfplumber fallback added | PASS | IPC additions return `marker_failed`; no fallback call was added. |
| 7. Queue v0 semantics remain intact | PASS | `process_next_ipc()` delegates through existing `process_next()` state handling; targeted tests pass. |
| 8. CLI warm-process exists and carries L1 gate language | PASS WITH CAVEAT | Top-level help and runtime output carry L1 gate language; `warm-process --help` itself only shows options. |
| 9. Rerun plan uses simple candidates and avoids arXiv rate-limit trap | FAIL | Rate-limit cooldown/precheck guardrails exist, but candidate readiness and enqueue syntax are not sufficient. |
| 10. No SVM/trading/L2/L4 changes occurred | PASS | Changed code paths are Marker queue/fetcher/CLI/tests plus docs/Dockerfile. L2/L4 remain documented as blocked/stubbed. |
| 11. Live validation was not rerun during fix/prep | PASS | Fix log and rerun plan state no live run; artifact directory contains only prior `warm_process_20260507*` logs, no rerun log. |

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md`
- `docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md`
- `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md`
- `docs/INDEX.md`
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `packages/research/ingestion/marker_ipc_worker.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `Dockerfile.ris`
- `tests/test_ris_marker_ipc_worker.py`
- `tests/test_ris_marker_queue.py`

## Commands Run

### `git status --short`

Exit code: 0

```text
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### `git log --oneline -5`

Exit code: 0

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `python -m polytool --help`

Exit code: 0. CLI loaded successfully; `research-marker-queue` is present.

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 126 items

tests\test_ris_marker_ipc_worker.py .................................... [ 28%]
...                                                                      [ 30%]
tests\test_ris_marker_queue.py ......................................... [ 63%]
...................s..........................                           [100%]

======================= 125 passed, 1 skipped in 2.19s ========================
```

### `python -m polytool research-marker-queue --help`

Exit code: 0

```text
usage: polytool research-marker-queue [-h] [--queue-dir PATH]
                                      {enqueue,list,process,warm-process,counts}
                                      ...

Marker Canonical Academic Parse Queue v0. Enqueue arXiv papers, process them
with Marker, and track which papers are RAG-ready (marker_ready=true). On
Windows, Marker models are pre-loaded once per batch (warm). On Linux/Docker,
models reload per paper (subprocess mode; warm IPC worker is v1).

positional arguments:
  {enqueue,list,process,warm-process,counts}
    enqueue             Add one arXiv paper to the parse queue
    list                Show queue items
    process             Process next N pending items using Marker. Warm batch
                        on Windows (thread mode); cold per paper on
                        Linux/Docker.
    warm-process        Process next N pending items using MarkerIPCWorker
                        (warm IPC, Linux/Docker). On Windows, falls back to
                        warm thread worker. NOTE: L1 production gated - live
                        Docker/GPU validation required.

options:
  -h, --help            show this help message and exit
  --queue-dir PATH      Override artifact queue directory (default:
                        artifacts/research/marker_parse_queue)
```

### `python -m polytool research-marker-queue warm-process --help`

Exit code: 0

```text
usage: polytool research-marker-queue warm-process [-h] [--max-items N]
                                                   [--marker-timeout SECONDS]
                                                   [--json]

options:
  -h, --help            show this help message and exit
  --max-items N         Maximum number of pending items to process (default:
                        1)
  --marker-timeout SECONDS
                        Marker extraction timeout in seconds (default: 900)
  --json                Output results as JSON
```

### `python -m polytool research-marker-queue enqueue --help`

Exit code: 0

```text
usage: polytool research-marker-queue enqueue [-h] --url URL_OR_ID
                                              [--title TITLE] [--force]
                                              [--json]

options:
  -h, --help       show this help message and exit
  --url URL_OR_ID  arXiv URL or bare arXiv ID (e.g. 2604.24366)
  --title TITLE    Optional title hint (fetcher resolves from API if omitted)
  --force          Re-enqueue even if the paper already exists (resets to
                   pending)
  --json           Output result as JSON
```

### `git grep -n "L1 Marker production rollout unblocked\|production rollout unblocked\|L1.*unblocked" docs`

Exit code: 0

```text
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:15:resolved. *(The "L1 is unblocked" claim below was correct at this decision point. It is now
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:80:## Is L1 unblocked? *(stale - see note below)*
docs/obsidian-vault/Claude Desktop/Current-Focus.md:56:- **2026-05-03**: Academic pipeline hosting decision accepted. Docker GPU passthrough verified (RTX 2070 Super, CUDA 13.2, `docker run --gpus all` succeeds). Q1->B (Docker+GPU dev machine), Q2->confirmed, Q3->moot, Q4->academic on dev / others on partner, Q5->volume-mount host cache. ~~L1 Marker production rollout unblocked.~~ *(stale - hosting blocker resolved but L1 re-blocked: Docker IPC warm-worker live validation failed 2026-05-07; L1 remains blocked pending >=3 warm papers at <=10s/paper.)* Next packet: [[Work-Packet - Marker Structural Parser Integration]]. Dev log: `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`.
```

### `git diff --stat`

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  12 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |   6 +
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            |  66 ++++++
 packages/research/ingestion/marker_queue.py        |  98 +++++++++
 tests/test_ris_marker_queue.py                     | 236 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 114 ++++++++++
 11 files changed, 548 insertions(+), 8 deletions(-)
```

### `git diff --name-status`

Exit code: 0

```text
M	Dockerfile.ris
M	docs/INDEX.md
M	docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### Artifact check for rerun logs

Command:

```powershell
if (Test-Path artifacts/research/marker_ipc_validation) { Get-ChildItem artifacts/research/marker_ipc_validation -File | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 200 } else { 'MISSING artifacts/research/marker_ipc_validation' }
```

Exit code: 0

```text
Name                           Length LastWriteTime
----                           ------ -------------
warm_process_20260507.log        1988 5/7/2026 11:56:34 AM
warm_process_20260507_run2.log   6583 5/7/2026 12:16:30 PM
warm_process_20260507_run3.log   3246 5/7/2026 12:37:40 PM
warm_process_20260507_run4.log   3265 5/7/2026 12:42:18 PM
```

No `warm_process_rerun_*` log was present.

## Blockers / Required Fixes

1. Fix rerun-plan enqueue syntax:
   - `python -m polytool research-marker-queue enqueue --url 2604.24366 --force`
   - `python -m polytool research-marker-queue enqueue --url <arxiv_id> --title "hint title"`
2. Replace the checked readiness list with unchecked prerequisites unless there
   is evidence that the Docker build, queue reset, and paper verification have
   actually completed.
3. Provide an exact three-paper validation queue. Either verify `2204.05149`
   and replace/exclude `2412.14173` with a concrete command/path, or use a
   fresh validation queue directory containing only three verified simple papers.
4. Optional cleanup: repeat the L1 gate wording in `warm-process --help` itself,
   not only the top-level command help and runtime output.

## Codex Review Summary

Tier: skip/read-only validation review. No trading, SVM implementation, risk,
execution, L2, or L4 code was reviewed or changed.

Issues found: rerun plan is not currently executable/safe; second live Docker
validation should not be attempted until the plan blockers above are fixed.

Issues addressed: none. Per instruction, no code, queue, artifact, Docker run,
or existing docs were modified. This review dev log is the only file created.
