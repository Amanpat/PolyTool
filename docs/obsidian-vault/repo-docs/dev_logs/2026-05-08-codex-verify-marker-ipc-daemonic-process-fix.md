---
title: Codex Verify Marker Ipc Daemonic Process Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemonic-process-fix.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker IPC Daemonic Process Fix

Date: 2026-05-08
Type: read-only verification review
Scope: Marker Docker IPC warm-worker v1 daemon-process fix
Verdict: PASS

---

## Summary

PASS. The root cause from the prior direct-PDF live validation,
`daemonic processes are not allowed to have children`, is addressed in the IPC
worker code: the warm worker process is now created with `daemon=False`, and
`restart()` creates the replacement worker through the same non-daemon `start()`
path.

Docker rebuild plus one direct-PDF live validation may run next. L1 remains
blocked until that live validation passes with at least three Marker-ready
papers in one warm-worker session and papers 2+ at <=10s parse time.

No code, queue artifact, Docker, live Marker, SVM/trading/L2/L4, or validation
artifact changes were made by this Codex review. This review only created this
dev log.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md`
- `docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md`
- `docs/dev_logs/2026-05-08_claude-review-marker-ipc-daemonic-process-fix.md`
- `packages/research/ingestion/marker_ipc_worker.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `tests/test_ris_marker_queue.py`
- Changed-file scope from `git status --short`, `git diff --stat`, and `git diff --name-status`

---

## Verification Findings

1. Root cause addressed: `packages/research/ingestion/marker_ipc_worker.py`
   has `_make_process(..., daemon=False)` by default, and `start()` explicitly
   passes `daemon=False` when creating the worker process. The inline comment
   names the Python daemon-child restriction and the prior live failure.

2. Restart safety: `MarkerIPCWorker.restart()` terminates an existing live worker
   or clears stale references, then calls `self.start()`. It cannot create a
   replacement daemon process unless a test-injected process factory ignores the
   argument. The production path receives `daemon=False`.

3. Test coverage is present and passing:
   - `TestMarkerIPCWorkerDaemonSafety.test_start_passes_daemon_false_to_factory`
   - `TestMarkerIPCWorkerDaemonSafety.test_restart_passes_daemon_false_to_factory`
   - `TestMarkerIPCWorkerDaemonSafety.test_multi_parse_paper1_ok_paper2_ok`
   - `TestMarkerIPCWorkerDaemonSafety.test_worker_survives_daemonic_error_and_next_paper_succeeds`
   - `TestProcessNextIPCDaemonSafety.test_two_paper_session_both_done`
   - `TestProcessNextIPCDaemonSafety.test_daemonic_error_from_marker_internals_is_retryable`
   - `TestProcessNextIPCDaemonSafety.test_direct_pdf_path_two_papers_both_done`

4. Direct-PDF validation path remains intact:
   - `research-marker-queue enqueue --pdf-url` is still exposed.
   - `MarkerParseQueue.enqueue(..., pdf_url=...)` stores `pdf_url`.
   - `_process_item()` routes `pdf_url` items to `fetch_pdf_direct()`.
   - `LiveAcademicFetcher.fetch_pdf_direct()` skips arXiv metadata and delegates
     to the same `_parse_pdf()` path, so injected IPC workers are used.

5. IPC failures still do not set `_MARKER_DISABLED`: the IPC path enters
   `_marker_ipc_worker_extract()`, which calls `self._ipc_worker.parse()` and
   returns `marker_failed` metadata on error. The only `_MARKER_DISABLED.set()`
   calls remain in the non-IPC thread/subprocess/auto fallback paths.

6. No pdfplumber fallback was added to the IPC path. IPC errors return
   `body_source=marker_failed`. Existing pdfplumber code remains in legacy/debug
   paths, not in `process_next_ipc()` or `_marker_ipc_worker_extract()`.

7. Queue semantics remain intact: `MAX_ATTEMPTS=3`, pending -> processing ->
   done/failed behavior, `is_marker_ready(body_source == "marker" and length >=
   threshold)`, and retryable Marker failures are unchanged. The exact live
   daemonic error remains retryable until max attempts.

8. Scope safety: the fix and review logs state no live Marker validation,
   Docker rebuild/prune, queue mutation, or Docker container start occurred
   during the fix. This review did not run Docker, live Marker, queue-mutating
   commands, or rebuild/prune commands. The tree contains pre-existing dirty
   Obsidian metadata, including one SVM smart-env metadata file, but no SVM
   source, trading, L2, or L4 source changes were part of the daemon fix.

9. L1 remains blocked in the governing docs until live validation passes.
   `docs/CURRENT_DEVELOPMENT.md` still says Marker L1 is blocked on Docker IPC
   warm-worker validation, and the warm-worker packet says L2 remains blocked
   until Feature 3 passes.

10. Next step if accepted: rebuild the RIS Docker image, then run one direct-PDF
    live validation via `warm-process --max-items 3 --json` using a fresh or
    reset direct-PDF queue.

---

## Commands Run

### `git status --short`

Exit code: 0

```text
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
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
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-rerun-plan-fixed.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-preflight-queue.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md
?? docs/dev_logs/2026-05-08_claude-review-marker-ipc-daemonic-process-fix.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-goal-loop.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-validation-queue.md
?? docs/dev_logs/2026-05-08_marker-ipc-live-validation-preflight-completion.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
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

Exit code: 0. The CLI loaded and included `research-marker-queue` in the RIS command list.

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 155 items

tests\test_ris_marker_ipc_worker.py .................................... [ 23%]
........                                                                 [ 28%]
tests\test_ris_marker_queue.py ......................................... [ 54%]
...................s..................................................   [100%]

======================= 154 passed, 1 skipped in 3.19s ========================
```

### `python -m polytool research-marker-queue enqueue --help`

Exit code: 0

```text
usage: polytool research-marker-queue enqueue [-h] --url URL_OR_ID
                                              [--title TITLE]
                                              [--pdf-url PDF_URL_OR_PATH]
                                              [--force] [--json]

options:
  -h, --help            show this help message and exit
  --url URL_OR_ID       arXiv URL or bare arXiv ID (e.g. 2604.24366)
  --title TITLE         Optional title hint (fetcher resolves from API if
                        omitted)
  --pdf-url PDF_URL_OR_PATH
                        Direct PDF URL or local file path. When set, warm-
                        process skips the arXiv metadata API (no
                        export.arxiv.org query) and fetches/reads the PDF
                        directly. Useful when the Atom API is rate-limited.
                        --url still determines candidate_id.
  --force               Re-enqueue even if the paper already exists (resets to
                        pending)
  --json                Output result as JSON
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

### `git diff --stat`

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  97 ++-
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 ++++---
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  31 +-
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            | 137 +++++
 packages/research/ingestion/marker_queue.py        | 112 +++-
 tests/test_ris_marker_queue.py                     | 663 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 ++++-
 13 files changed, 1228 insertions(+), 182 deletions(-)
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

Note: untracked new files such as `packages/research/ingestion/marker_ipc_worker.py`
and `tests/test_ris_marker_ipc_worker.py` do not appear in `git diff --stat`.

### `git diff --name-status`

Exit code: 0

```text
M	Dockerfile.ris
M	docs/INDEX.md
M	docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### Scope inspection commands

The review also used read-only `rg`, `Select-String`, `Get-Content`, and targeted
`git diff -- <path>` commands to inspect:

- daemon process creation/restart code
- IPC failure behavior
- `_MARKER_DISABLED` and pdfplumber references
- direct-PDF enqueue/fetch/process path
- queue retry semantics
- L1/L2/SVM/trading scope references
- prior fix and review dev logs

No shell command in this review rebuilt Docker, pruned Docker, ran a live Marker
job, mutated queues, or changed files outside this dev log.

---

## Decisions

- PASS the daemon-process fix for the next step.
- The next prompt may rebuild the Docker image and rerun one direct-PDF live
  validation.
- The live validation should use a fresh/reset direct-PDF queue because the prior
  direct queue still had retry state from the failed run.
- L1 must remain blocked until the live run passes the warm-throughput gate.

---

## Open Questions / Blockers

No code blockers found for Docker rebuild plus one direct-PDF live validation.

Residual live-only risk: `daemon=False` removes Python's parent daemon-process
restriction for the IPC worker. A deeper Marker/ONNX/torch child process could
still fail in live GPU validation, but that cannot be proven or disproven by
offline tests.

---

## Codex Review Summary

Tier: recommended review (research ingestion and queue code). Mandatory trading,
execution, kill-switch, risk manager, and rate limiter files were not in scope.

Issues found: none blocking. The fix is ready for Docker rebuild and one
direct-PDF live validation. L1 remains blocked until that validation passes.
