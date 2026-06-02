---
title: Codex Verify Marker Ipc Direct Pdf Live Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify - Marker IPC Direct-PDF Live Validation

Date: 2026-05-08
Type: read-only validation review
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1, direct-PDF live validation
Verdict: **FAIL**

## Decision

**FAIL.** Feature 3 live gates are not met, and Feature 3 closeout may **not**
run next.

The live Docker/GPU validation did run against the direct-PDF queue, but only
one paper completed in the warm-worker session. Paper 2 failed twice with:

```text
daemonic processes are not allowed to have children
```

Paper 3 was never attempted. L1 Marker production rollout remains blocked.

## Files Changed

- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md`
  - Added this review log only.

No code, tests, Docker files, queue artifacts, validation artifacts, SVM files,
trading files, L2 files, or L4 files were edited by this review.

## Artifacts and Logs Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md`
- `docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md`
- `artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_104137.log`
- `artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log`
- `artifacts/research/marker_ipc_validation/validation_run.json`
- `artifacts/research/marker_ipc_validation/warm_process_20260507.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run2.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run3.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run4.log`
- `artifacts/research/marker_validation_queue_direct/queue.jsonl`
- `artifacts/research/marker_validation_queue_direct/results.jsonl`

## Gate-by-Gate Review

| # | Gate | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Live validation used Docker/Linux/GPU, not only local mocks | PASS | Live log used `docker --context default run --rm --gpus all` with image `polytool-ris-scheduler-gpu:latest`; raw log contains Marker progress output. |
| 2 | Container used current repo code | PASS WITH CAVEAT | `--pdf-url` was available and `fetch_pdf_direct: FOUND`; image package was stale, so the run used a bind mount of current `packages/research` into site-packages. |
| 3 | At least 3 papers completed in one warm-worker session | FAIL | Queue after run: `done=1`, `pending=2`, `failed=0`, `total=3`. |
| 4 | Papers 2+ each parse at `<=10s` | FAIL | Paper 2 failed before Marker inference twice; paper 3 was never attempted. |
| 5 | `ipc_warm_worker_used=true` on completed results | PASS WITH CAVEAT | Live JSON output shows true for the completed paper and top-level result; persisted `results.jsonl` does not include that field. |
| 6 | `body_source=marker`; no pdfplumber fallback | FAIL FOR ACCEPTANCE, PASS FOR NO FALLBACK | Only paper 1 completed with `body_source=marker`; paper 2 results were `marker_failed`; no `pdfplumber` or `pdfplumber_fallback` appeared. |
| 7 | Queue results/state semantics remain intact | PASS | Retryable failures stayed `pending` with attempts incremented; no item stuck in `processing`; failure reasons persisted in results. This matches queue code/tests: retryable failure remains pending until max attempts. |
| 8 | Clean shutdown/no orphan process evidence exists | PASS | Live log says Docker containers were empty before/after; this review's `docker ps` check showed no running containers. |
| 9 | No Docker rebuild/prune/code/test/SVM/trading/L2/L4 changes occurred during live validation | PASS WITH CAVEAT | The tree was already dirty before validation. Live log shows a `docker run`, no build/prune; scoped checks show no SVM/trading status changes, and L2/L4 remain docs-only references. |
| 10 | L1 has not yet been marked unblocked in docs | PASS | `CURRENT_DEVELOPMENT.md`, `INDEX.md`, and the Marker feature doc still say L1 production is blocked pending warm-worker validation. |
| 11 | Low-disk risk was recorded | PASS | Live log recorded `40.49 GB free` before and after; hard stop threshold was 1 GB and did not trigger. |

## Per-Paper Timing Table

Acceptance requires at least 3 completed papers in one warm-worker session and
papers 2+ at `parse_seconds <= 10`.

| Paper | Attempt | Candidate | Queue status | Body source | Parse seconds | Total seconds | IPC warm worker | Failure reason |
|-------|---------|-----------|--------------|-------------|---------------|---------------|-----------------|----------------|
| 1 | 1 | `arxiv:2604.24366` | done | marker | 51.62 | 112.27 | true | null |
| 2 | 1 | `arxiv:2109.07581` | pending | marker_failed | 0.0 | 0.24 | true | daemonic processes are not allowed to have children |
| 2 | 2 | `arxiv:2109.07581` | pending | marker_failed | 0.0 | 0.15 | true | daemonic processes are not allowed to have children |
| 3 | 0 | `arxiv:1910.08858` | pending | never attempted | n/a | n/a | n/a | n/a |

## Blockers and Fixes

Blocking:

- The warm-worker path fails on paper 2+ with `daemonic processes are not
  allowed to have children`.
- Only 1 of 3 required papers completed.
- Papers 2+ did not demonstrate warm throughput at `<=10s`.

Recommended next fix:

- Investigate the process model in `packages/research/ingestion/marker_ipc_worker.py`
  and/or `packages/research/ingestion/marker_queue.py`. The worker must not
  attempt to spawn child processes from a daemonic process context during
  sequential warm parsing.
- After a code fix, rebuild the stale Docker image or otherwise make current
  repo code available without the site-packages overlay workaround, then prepare
  a fresh direct-PDF queue and run a new operator-approved validation.

## Commands Run and Outputs

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
?? docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-goal-loop.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
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

### `git diff --stat`

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  97 ++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++++---
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  31 +-
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            | 137 +++++
 packages/research/ingestion/marker_queue.py        | 112 +++-
 tests/test_ris_marker_queue.py                     | 576 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 ++++-
 13 files changed, 1141 insertions(+), 182 deletions(-)
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
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

### `python -B -m polytool --help`

Exit code: 0

Relevant output:

```text
research-marker-queue     Enqueue/process arXiv papers through Marker; track RAG-ready status
```

### `Get-ChildItem -Path docs/dev_logs -Filter '*marker-ipc-direct-pdf-live-validation*.md'`

Exit code: 0

```text
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-ipc-direct-pdf-live-validation.md
```

### `Get-ChildItem -Recurse -Force artifacts/research/marker_ipc_validation`

Exit code: 0

```text
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\direct_pdf_live_20260508_104137.log
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\direct_pdf_live_20260508_105302.log
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\validation_run.json
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run3.log
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run4.log
```

### `Get-ChildItem -Recurse -Force artifacts/research/marker_validation_queue_direct`

Exit code: 0

```text
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_validation_queue_direct\queue.jsonl
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_validation_queue_direct\results.jsonl
```

### `docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Command}}"`

Exit code: 0

```text
NAMES     IMAGE     STATUS    COMMAND
```

No running Docker containers were present.

### `Get-Content -Raw artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log`

Exit code: 0

Key output:

```json
{
  "processed": [
    {
      "candidate_id": "arxiv:2604.24366",
      "source_url": "https://arxiv.org/abs/2604.24366",
      "arxiv_id": "2604.24366",
      "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book",
      "body_source": "marker",
      "body_length": 56923,
      "parse_seconds": 51.62,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 112.27,
      "processed_at": "2026-05-08T14:54:56.254278+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:2109.07581",
      "source_url": "https://arxiv.org/abs/2109.07581",
      "arxiv_id": "2109.07581",
      "title": "The Impact of COVID-19 on Sports Betting Markets",
      "body_source": "marker_failed",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "daemonic processes are not allowed to have children",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.24,
      "processed_at": "2026-05-08T14:54:56.521825+00:00",
      "attempt": 1,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:2109.07581",
      "source_url": "https://arxiv.org/abs/2109.07581",
      "arxiv_id": "2109.07581",
      "title": "The Impact of COVID-19 on Sports Betting Markets",
      "body_source": "marker_failed",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "daemonic processes are not allowed to have children",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.15,
      "processed_at": "2026-05-08T14:54:56.696248+00:00",
      "attempt": 2,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

The same log also contains Marker progress bars, proving a real Marker parse
ran for paper 1 rather than a local mock.

### `Get-Content -Raw artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_104137.log`

Exit code: 0

```text
ModuleNotFoundError: No module named 'packages.research.ingestion'
```

This was an earlier failed container invocation before the site-packages overlay
made the current repo's `packages/research` code visible.

### `Get-Content -Raw artifacts/research/marker_ipc_validation/validation_run.json`

Exit code: 0

Key output:

```json
{
  "processed": [
    {
      "candidate_id": "arxiv:2604.24366",
      "body_source": "marker",
      "body_length": 56923,
      "parse_seconds": 39.19,
      "marker_ready": true,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "body_source": "error",
      "parse_seconds": 0.0,
      "failure_reason": "Timeout fetching http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "body_source": "error",
      "parse_seconds": 0.0,
      "failure_reason": "HTTP 429 Unknown Error for http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

This older artifact is not sufficient acceptance evidence because the later
direct-PDF live run is the relevant validation and failed on paper 2.

### `Get-Content -Raw artifacts/research/marker_validation_queue_direct/queue.jsonl`

Exit code: 0

```json
{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book","status":"done","attempts":1,"created_at":"2026-05-08T14:26:57.703795+00:00","updated_at":"2026-05-08T14:54:56.254278+00:00","pdf_url":"https://arxiv.org/pdf/2604.24366.pdf"}
{"candidate_id":"arxiv:2109.07581","source_url":"https://arxiv.org/abs/2109.07581","arxiv_id":"2109.07581","title":"The Impact of COVID-19 on Sports Betting Markets","status":"pending","attempts":2,"created_at":"2026-05-08T14:26:58.217995+00:00","updated_at":"2026-05-08T14:54:56.696248+00:00","pdf_url":"https://arxiv.org/pdf/2109.07581.pdf"}
{"candidate_id":"arxiv:1910.08858","source_url":"https://arxiv.org/abs/1910.08858","arxiv_id":"1910.08858","title":"Beating the House: Identifying Inefficiencies in Sports Betting Markets","status":"pending","attempts":0,"created_at":"2026-05-08T14:26:58.735760+00:00","updated_at":"2026-05-08T14:26:58.735760+00:00","pdf_url":"https://arxiv.org/pdf/1910.08858.pdf"}
```

### `Get-Content -Raw artifacts/research/marker_validation_queue_direct/results.jsonl`

Exit code: 0

```json
{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book","body_source":"marker","body_length":56923,"parse_seconds":51.62,"failure_reason":null,"rejected":false,"exit_code":0,"marker_ready":true,"total_seconds":112.27,"processed_at":"2026-05-08T14:54:56.254278+00:00","attempt":1,"queue_status":"done"}
{"candidate_id":"arxiv:2109.07581","source_url":"https://arxiv.org/abs/2109.07581","arxiv_id":"2109.07581","title":"The Impact of COVID-19 on Sports Betting Markets","body_source":"marker_failed","body_length":0,"parse_seconds":0.0,"failure_reason":"daemonic processes are not allowed to have children","rejected":true,"exit_code":1,"marker_ready":false,"total_seconds":0.24,"processed_at":"2026-05-08T14:54:56.521825+00:00","attempt":1,"queue_status":"pending"}
{"candidate_id":"arxiv:2109.07581","source_url":"https://arxiv.org/abs/2109.07581","arxiv_id":"2109.07581","title":"The Impact of COVID-19 on Sports Betting Markets","body_source":"marker_failed","body_length":0,"parse_seconds":0.0,"failure_reason":"daemonic processes are not allowed to have children","rejected":true,"exit_code":1,"marker_ready":false,"total_seconds":0.15,"processed_at":"2026-05-08T14:54:56.696248+00:00","attempt":2,"queue_status":"pending"}
```

### `python -B -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue_direct counts --json`

Exit code: 0

```json
{
  "pending": 2,
  "processing": 0,
  "done": 1,
  "failed": 0,
  "total": 3
}
```

### `python -B -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue_direct list --json`

Exit code: 0

```json
[
  {
    "candidate_id": "arxiv:2604.24366",
    "source_url": "https://arxiv.org/abs/2604.24366",
    "arxiv_id": "2604.24366",
    "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book",
    "status": "done",
    "attempts": 1,
    "created_at": "2026-05-08T14:26:57.703795+00:00",
    "updated_at": "2026-05-08T14:54:56.254278+00:00",
    "pdf_url": "https://arxiv.org/pdf/2604.24366.pdf"
  },
  {
    "candidate_id": "arxiv:2109.07581",
    "source_url": "https://arxiv.org/abs/2109.07581",
    "arxiv_id": "2109.07581",
    "title": "The Impact of COVID-19 on Sports Betting Markets",
    "status": "pending",
    "attempts": 2,
    "created_at": "2026-05-08T14:26:58.217995+00:00",
    "updated_at": "2026-05-08T14:54:56.696248+00:00",
    "pdf_url": "https://arxiv.org/pdf/2109.07581.pdf"
  },
  {
    "candidate_id": "arxiv:1910.08858",
    "source_url": "https://arxiv.org/abs/1910.08858",
    "arxiv_id": "1910.08858",
    "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
    "status": "pending",
    "attempts": 0,
    "created_at": "2026-05-08T14:26:58.735760+00:00",
    "updated_at": "2026-05-08T14:26:58.735760+00:00",
    "pdf_url": "https://arxiv.org/pdf/1910.08858.pdf"
  }
]
```

### Queue semantics check

Command:

```powershell
rg -n "status|pending|processing|done|failed|max_attempts|marker_failed|queue_status" packages/research/ingestion/marker_queue.py
```

Relevant output:

```text
11:  pending -> processing -> done
12:                       -> pending  (retryable failure, attempts < MAX_ATTEMPTS)
13:                       -> failed   (terminal after MAX_ATTEMPTS)
17:  pdfplumber, pdfplumber_fallback, abstract_fallback, marker_failed: NOT marker_ready.
300:                final_status = "done"
302:                final_status = "failed"
304:                final_status = "pending"  # retryable
321:                "queue_status": final_status,
```

Command:

```powershell
rg -n "max_attempts|pending|failed|queue_status|marker_failed" tests/test_ris_marker_queue.py
```

Relevant output:

```text
14:- retry logic: attempts increment; after MAX_ATTEMPTS -> failed
387:    def test_marker_failed_stays_pending_until_max_attempts(self, tmp_path: Path) -> None:
399:    def test_marker_failed_becomes_failed_after_max_attempts(self, tmp_path: Path) -> None:
1017:        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(_failed_raw()))
1020:        assert r["queue_status"] == "pending"  # first failure -> retryable
1037:    def test_ipc_failure_terminal_after_max_attempts(self, tmp_path: Path) -> None:
1213:    def test_ipc_error_returns_marker_failed_not_pdfplumber(self) -> None:
```

### L1 blocked/unblocked doc check

Command:

```powershell
rg -n "L1|unblocked|BLOCKED|blocked|Marker production rollout|Marker Production" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/features docs/INDEX.md
```

Relevant output:

```text
docs/INDEX.md:118:| [RIS Marker Structural Parser - Production Default (Layer 1)](features/ris-marker-structural-parser-scaffold.md) | **CODE COMPLETE - L1 PRODUCTION BLOCKED (awaiting Docker IPC warm-worker v1).** Queue v0 shipped 2026-05-05 (queue, CLI, indexing gate, failure semantics, 43 tests; Codex re-review PASS). Docker IPC warm-worker deferred to v1. pdfplumber is legacy/debug only. `body_source=marker` is the RAG-readiness gate. |
docs/CURRENT_DEVELOPMENT.md:94:| Marker Canonical Academic Parse Queue v0 | RIS | `docs/features/ris-marker-structural-parser-scaffold.md` - file-backed queue, CLI surface, `is_marker_ready()` gate, Marker-only `IngestPipeline` gate, short-body rejection (retryable/terminal), honest platform docs. 43 tests; Codex re-review PASS. Docker IPC warm-worker deferred to v1. L1 Marker production rollout still blocked on IPC worker. |
docs/CURRENT_DEVELOPMENT.md:95:| Marker Single-Paper Validation Control Surface | `run-academic-url` subcommand; process-boundary subprocess cancel; `parse_seconds` in result; 5 new tests. Validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. L1 production still blocked on <=10s/paper gate. |
docs/CURRENT_DEVELOPMENT.md:115:| RIS L1 Marker Production Rollout - Validation | 2026-05-05 | Operator chose Option A 2026-05-05: async parse queue. Queue v0 complete (Codex re-review PASS). Blocked on Docker IPC warm-worker (v1). pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. | Docker IPC warm-worker (v1) ships; warm worker validates >=3 papers with `parse_seconds <=10s` for papers 2+ |
docs/CURRENT_DEVELOPMENT.md:139:- **RIS Marker Canonical Academic Parse Queue v0 is COMPLETE (2026-05-05).** Queue, CLI surface, `is_marker_ready()` gate, Marker-only academic indexing gate (`IngestPipeline`), short-body rejection, honest platform docs, 43 tests. Codex re-review PASS. Feature doc: `docs/features/ris-marker-structural-parser-scaffold.md`. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. **Docker IPC warm-worker (v1) is deferred** - multi-paper warm-throughput validation may NOT proceed as an L1 acceptance gate until v1 IPC warm-worker ships. Do NOT start L2 until warm-worker validates >=3 papers warm. **L1 Marker Production Rollout remains PAUSED** - blocked on Docker IPC warm-worker v1.
docs/features/ris-marker-structural-parser-scaffold.md:3:**Status: CODE COMPLETE - L1 PRODUCTION BLOCKED (awaiting async queue implementation, 2026-05-05)**
docs/features/ris-marker-structural-parser-scaffold.md:14:> L1 production rollout resumes when the async queue ships and warm worker validates >=3 papers at <=10s/paper.
```

### SVM/trading scoped status check

Command:

```powershell
git status --short -- packages/research/relevance_filter tools/cli/research_prefetch_svm_train.py tools/cli/research_prefetch_discover.py tools/cli/research_acquire.py tests/test_ris_svm_filter.py execution packages/polymarket packages/simtrader polytool/simtrader tools/cli/simtrader.py risk_manager.py rate_limiter.py kill_switch.py
```

Exit code: 0

```text
<no output>
```

### L2/L4 path check

Command:

```powershell
rg --files | rg -i "paperqa|multi.source|multi-source|harvester|academic_harvest|l4"
```

Exit code: 0

```text
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - PaperQA2 RAG Control Flow.md
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Multi-source Academic Harvesters.md
```

### Build/prune check in validation evidence

Command:

```powershell
rg -n -- "docker (build|compose build|builder|system prune|image prune|container prune|volume prune|prune)|docker --context default build|docker compose build" docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_104137.log
```

Exit code: 1

```text
<no output>
```

No build or prune command was found in the direct-PDF validation evidence.

### Evidence grep

Command:

```powershell
rg -n -- "--gpus all|polytool-ris-scheduler-gpu|/usr/local/lib/python3.11/site-packages/packages/research|--pdf-url|IMPORT OK|fetch_pdf_direct|C drive free|Before:|After:|40.49|docker ps|no containers|none running|daemonic processes" docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_104137.log
```

Exit code: 0

```text
artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_104137.log:4:+ ... h $logfile; docker --context default run --rm --gpus all -v "${pwd_wi ...
artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log:4:+ ... ct -FilePath $logfile; docker --context default run --rm --gpus all `
artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log:92:      "failure_reason": "daemonic processes are not allowed to have children",
artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log:110:      "failure_reason": "daemonic processes are not allowed to have children",
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:37:### C drive free space
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:39:- **Before run:** 40.49 GB free / 230.87 GB total
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:40:- **After run:** 40.49 GB free (no measurable change)
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:47:(none running)
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:66:--pdf-url PDF_URL_OR_PATH
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:70:`--pdf-url` present: current code is visible.
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:81:-v "${PWD}/packages/research:/usr/local/lib/python3.11/site-packages/packages/research"
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:86:IMPORT OK
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:87:fetch_pdf_direct: FOUND
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:95:docker --context default run --rm --gpus all `
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:97:  -v "D:\Coding Projects\Polymarket\PolyTool/packages/research:/usr/local/lib/python3.11/site-packages/packages/research" `
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:100:  polytool-ris-scheduler-gpu:latest `
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:204:| Clean shutdown, no orphan worker | Container exits cleanly | `docker ps` empty after run; exit_code=0 from CLI | **PASS** |
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:259:(no containers running)
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:272:- Before: 40.49 GB free
docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md:273:- After: 40.49 GB free
```

## Tests and Live Jobs

No tests were run because this was a read-only validation review and no code was
changed.

No live Marker job was run by this review. The only Docker command run here was
the safe process check `docker ps`.

## Codex Review Summary

Tier: read-only validation review. Mandatory trading/risk execution files were
not in scope. Issues found: Feature 3 live validation fails; closeout must not
run. Issues addressed: none, per instruction to change only this review dev log.
