---
title: Codex Verify Marker Docker Ipc Worker Integration Fixed
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify Marker Docker IPC Worker Integration Fixed

Date: 2026-05-07
Type: read-only verification / review
Scope: review-only; no code changes. This dev log is the only file edited by Codex.
Verdict: PASS

## Objective

Verify the fixed Marker Docker/Linux IPC warm-worker integration before live
Docker/GPU validation. Done means a PASS/FAIL decision on whether the
Docker/live validation prompt may run next.

## Decision

PASS. Docker/live validation may run next.

This is not an L1 production unblock. The checked-out implementation exposes
and tests the explicit warm-worker path, but live Docker/GPU timing validation
is still pending and remains the blocker before L1 production rollout.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md`
- `docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md`
- `docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md`
- `packages/research/ingestion/marker_ipc_worker.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `tests/test_ris_marker_queue.py`

## Review Findings

Blocking findings: none.

Checks:

1. CLI exposes explicit warm-worker path: PASS. `research-marker-queue --help`
   lists `warm-process`.
2. Queue/fetcher import/use `MarkerIPCWorker`: PASS. `process_next_ipc()`
   lazy-imports `MarkerIPCWorker`; `LiveAcademicFetcher` accepts `_ipc_worker`
   and routes parsing through `_marker_ipc_worker_extract()`.
3. One worker can process multiple queue items in a session according to tests:
   PASS. IPC worker tests assert one model load across multiple parse calls,
   and queue tests route two queued papers through the same mock worker.
4. Worker entrypoint remains spawn-safe: PASS. `_marker_ipc_worker_main` remains
   module-level and default multiprocessing context is `spawn`.
5. Timeout/error handling does not set global `_MARKER_DISABLED`: PASS for the
   IPC path. The old cold subprocess/thread paths still have their pre-existing
   disabled-flag behavior, but the IPC path bypasses it and tests assert the
   flag is not set.
6. No pdfplumber production fallback added: PASS. IPC errors return
   `body_source=marker_failed`; readiness gates still reject pdfplumber bodies.
7. Queue v0 semantics remain intact: PASS. Pending/processing/done/failed,
   retry-to-terminal behavior, result records, counts, and `is_marker_ready()`
   are covered by the passing queue tests.
8. Windows thread mode remains unchanged: PASS. Ordinary `process` remains the
   v0 behavior; `warm-process` falls back to the warm thread path on Windows.
9. L1 production remains blocked pending live validation: PASS. Queue docstring
   and CLI output both state live Docker/GPU validation is still required.
10. L2/PaperQA2 and L4 remain blocked/stubbed: PASS. The work packet still
    gates L2 on warm-worker acceptance and states no L4 work.
11. SVM labels/models, trading files, Docker/config, and artifacts are
    untouched except allowed test temp files: PASS by git diff/status scope.
    No SVM, trading/execution, config, infra, Docker, or artifact paths appear
    in the tracked diff/status checks.
12. Live validation is still pending: PASS. No live Marker jobs or Docker/GPU
    validation commands were run in this review.

Non-blocking observation:

- The top-level queue CLI description still says Linux/Docker `process` mode
  reloads per paper and warm IPC worker is v1. That remains accurate for the
  ordinary `process` subcommand because the explicit path is `warm-process`.

## Commands Run and Results

### `git status --short`

Exit code: 0

```text
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

After this dev log is written, it will additionally appear as an untracked file.

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

Exit code: 0

Result: CLI loaded successfully and listed `research-marker-queue` as an
available RIS command.

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 120 items

tests\test_ris_marker_ipc_worker.py .................................    [ 27%]
tests\test_ris_marker_queue.py ......................................... [ 61%]
...................s..........................                           [100%]

======================= 119 passed, 1 skipped in 2.14s ========================
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
    counts              Show item counts by status

options:
  -h, --help            show this help message and exit
  --queue-dir PATH      Override artifact queue directory (default:
                        artifacts/research/marker_parse_queue)
```

Note: the terminal output used a Unicode dash before `live`; this log records it
with an ASCII hyphen for encoding safety.

### `git diff --stat`

Exit code: 0

```text
 packages/research/ingestion/fetchers.py     |  40 +++++
 packages/research/ingestion/marker_queue.py |  98 ++++++++++++
 tests/test_ris_marker_queue.py              | 236 ++++++++++++++++++++++++++++
 tools/cli/research_marker_queue.py          | 114 ++++++++++++++
 4 files changed, 488 insertions(+)
```

### `git diff --name-status`

Exit code: 0

```text
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### Scope status check

Command:

```text
git status --short packages tools tests config infra docker-compose.yml Dockerfile.ris artifacts
```

Exit code: 0

```text
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### Scope diff check

Command:

```text
git diff --name-status -- packages tools tests config infra docker-compose.yml Dockerfile.ris artifacts
```

Exit code: 0

```text
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

## Docker / Live Validation Readiness

Docker/live validation may run next.

The next validation should still be treated as live acceptance evidence, not
production rollout. It must confirm a real Docker/GPU warm session with multiple
papers, `body_source=marker`, `ipc_warm_worker_used=true`, and warm paper parse
times meeting the <=10s target for papers 2+.

## Open Blockers

- Live Docker/GPU Marker validation is still pending.
- L1 production remains blocked until live validation passes and is logged.
- L2/PaperQA2 and L4 remain blocked/stubbed.
- No code fixes are required before the Docker/live validation prompt.

## Codex Review Summary

Tier: Recommended review. Scope was RIS queue/fetcher/CLI and worker code, not
trading execution or mandatory live-capital files.

Issues found: no blockers. The fixed integration satisfies the pre-live
validation checks.

Issues addressed: none. Review-only task; no code changes were made.
