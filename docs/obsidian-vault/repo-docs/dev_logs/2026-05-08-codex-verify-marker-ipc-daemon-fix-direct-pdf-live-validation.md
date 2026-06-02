---
title: Codex Verify Marker Ipc Daemon Fix Direct Pdf Live Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemon-fix-direct-pdf-live-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker IPC Daemon-Fix Direct-PDF Live Validation

Date: 2026-05-08
Type: read-only verification review
Scope: Feature 3 Marker Docker IPC warm-worker v1 live validation after daemon=False fix
Verdict: FAIL

---

## Summary

FAIL. The live validation proves the daemon=False fix works functionally: the run used
Docker/Linux/GPU, current daemon=False code was bind-mounted into the container,
direct-PDF queue items were used, three papers completed in one warm-worker session,
all completed papers had `body_source=marker`, and the daemonic-process error did not
recur.

Feature 3 live gates are not met because papers 2 and 3 parsed in 69.73s and 48.31s,
which both exceed the required <=10s warm-paper gate. Feature 3 closeout may NOT run
next. L1 Marker production rollout remains blocked unless the operator explicitly
revises the timing gate or approves a new validation scope.

Additional artifact caveat: the live command JSON in
`artifacts/research/marker_ipc_validation/daemon_fix_direct_pdf_live_20260508_115111.log`
has `ipc_warm_worker_used=true` on all three processed results, but persisted
`artifacts/research/marker_validation_queue_direct/results.jsonl` does not include that
field. The queue status/results semantics otherwise remain intact (`done=3`,
`failed=0`).

This review changed only this dev log.

---

## Gate-by-Gate Review

| # | Gate | Evidence | Result |
|---|------|----------|--------|
| 1 | Live validation used Docker/Linux/GPU | Validation dev log command used `docker --context default run --rm --gpus all`; `docker ps` now empty. | PASS |
| 2 | Container used current daemon=False code and direct-PDF path | Validation dev log verified `daemon=False in start(): True` inside container with packages overlay; queue entries contain `pdf_url`; direct-PDF command used `--pdf-url`. | PASS |
| 3 | Three papers completed in one warm-worker session | Live JSON has 3 processed papers; queue counts are `done=3`, `pending=0`, `failed=0`. | PASS |
| 4 | Papers 2+ each parse at <=10s | Paper 2 = 69.73s; paper 3 = 48.31s. | FAIL |
| 5 | `ipc_warm_worker_used=true` on completed results | Live command JSON has true for all 3 processed results and top-level true. Persisted `results.jsonl` omits the field. | PASS with artifact caveat |
| 6 | `body_source=marker`; no pdfplumber fallback | Live JSON and `results.jsonl` show all 3 `body_source=marker`; no pdfplumber marker appears in live output. | PASS |
| 7 | Daemon-process error did not recur | `rg` over live log found no `daemonic`, traceback, exception, or error lines; exit_code=0. | PASS |
| 8 | Queue state/results semantics remain intact | Queue list shows 3 records, all `status=done`, `attempts=1`; results append has 3 marker-ready records. | PASS |
| 9 | Clean shutdown/no orphan process evidence exists | `docker ps` output has no running containers; validation dev log records `--rm` clean exit. | PASS |
| 10 | No Docker rebuild/prune/code/test/SVM/trading/L2/L4 changes during live validation unless documented | Validation dev log records no Docker rebuild/prune and bind-mount overlay use. Existing dirty code/test files predate this review; no SVM/trading/L2/L4 source changes found in validation evidence. | PASS |
| 11 | L1 has not yet been marked unblocked in docs | `docs/CURRENT_DEVELOPMENT.md`, `docs/INDEX.md`, and `Current-Focus.md` still state L1 is blocked/paused; stale unblocked text is struck through and annotated stale. | PASS |
| 12 | Low-disk risk was recorded | Validation dev log records C: free space before/after: 40.44 GB -> 40.42 GB, above 1 GB stop threshold. | PASS |

Overall result: FAIL because gate 4 fails.

---

## Per-Paper Timing

| Paper | candidate_id | parse_seconds | total_seconds | body_source | ipc_warm_worker_used | queue_status |
|-------|--------------|---------------|---------------|-------------|----------------------|--------------|
| 1 | arxiv:2604.24366 | 45.55 | 72.31 | marker | true in live JSON | done |
| 2 | arxiv:2109.07581 | 69.73 | 69.86 | marker | true in live JSON | done |
| 3 | arxiv:1910.08858 | 48.31 | 48.53 | marker | true in live JSON | done |

Papers 2 and 3 fail the <=10s timing gate.

---

## Artifact and Log Paths Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemonic-process-fix.md`
- `docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md`
- `artifacts/research/marker_ipc_validation/daemon_fix_direct_pdf_live_20260508_115111.log`
- `artifacts/research/marker_validation_queue_direct/queue.jsonl`
- `artifacts/research/marker_validation_queue_direct/results.jsonl`
- `packages/research/ingestion/marker_ipc_worker.py` (read-only inspection)
- `packages/research/ingestion/marker_queue.py` (read-only inspection)
- `packages/research/ingestion/fetchers.py` (read-only inspection)
- `tools/cli/research_marker_queue.py` (read-only inspection)
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`

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
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemonic-process-fix.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
?? docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md
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

Exit code: 0. CLI loaded successfully and listed `research-marker-queue` under RIS
commands. Full help output was 100+ lines and was inspected for command availability.

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

### `Get-ChildItem artifacts/research/marker_ipc_validation`

Exit code: 0

```text
Mode   Length LastWriteTime        Name
----   ------ -------------        ----
-a----   3890 5/8/2026 11:54:34 AM daemon_fix_direct_pdf_live_20260508_115111.log
-a----   2962 5/8/2026 10:41:39 AM direct_pdf_live_20260508_104137.log
-a----  11464 5/8/2026 10:54:58 AM direct_pdf_live_20260508_105302.log
-a----   4264 5/8/2026 9:48:15 AM  validation_run.json
-a----   1988 5/7/2026 11:56:34 AM warm_process_20260507.log
-a----   6583 5/7/2026 12:16:30 PM warm_process_20260507_run2.log
-a----   3246 5/7/2026 12:37:40 PM warm_process_20260507_run3.log
-a----   3265 5/7/2026 12:42:18 PM warm_process_20260507_run4.log
```

### `Get-ChildItem artifacts/research/marker_validation_queue_direct`

Exit code: 0

```text
Mode   Length LastWriteTime        Name
----   ------ -------------        ----
-a----   1102 5/8/2026 11:54:32 AM queue.jsonl
-a----   1312 5/8/2026 11:54:32 AM results.jsonl
```

### `docker ps --format "table {{.Names}}`t{{.Image}}`t{{.Status}}`t{{.Command}}"`

Exit code: 0

```text
NAMES     IMAGE     STATUS    COMMAND
```

### `python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue_direct counts --json`

Exit code: 0

```json
{
  "pending": 0,
  "processing": 0,
  "done": 3,
  "failed": 0,
  "total": 3
}
```

### `python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue_direct list --json`

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
    "created_at": "2026-05-08T15:49:37.530890+00:00",
    "updated_at": "2026-05-08T15:52:33.945798+00:00",
    "pdf_url": "https://arxiv.org/pdf/2604.24366.pdf"
  },
  {
    "candidate_id": "arxiv:2109.07581",
    "source_url": "https://arxiv.org/abs/2109.07581",
    "arxiv_id": "2109.07581",
    "title": "The Impact of COVID-19 on Sports Betting Markets",
    "status": "done",
    "attempts": 1,
    "created_at": "2026-05-08T15:49:48.266368+00:00",
    "updated_at": "2026-05-08T15:53:43.927252+00:00",
    "pdf_url": "https://arxiv.org/pdf/2109.07581.pdf"
  },
  {
    "candidate_id": "arxiv:1910.08858",
    "source_url": "https://arxiv.org/abs/1910.08858",
    "arxiv_id": "1910.08858",
    "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
    "status": "done",
    "attempts": 1,
    "created_at": "2026-05-08T15:49:48.823716+00:00",
    "updated_at": "2026-05-08T15:54:32.519493+00:00",
    "pdf_url": "https://arxiv.org/pdf/1910.08858.pdf"
  }
]
```

### `Get-Content artifacts/research/marker_validation_queue_direct/results.jsonl`

Exit code: 0

```json
{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book","body_source":"marker","body_length":56923,"parse_seconds":45.55,"failure_reason":null,"rejected":false,"exit_code":0,"marker_ready":true,"total_seconds":72.31,"processed_at":"2026-05-08T15:52:33.945798+00:00","attempt":1,"queue_status":"done"}
{"candidate_id":"arxiv:2109.07581","source_url":"https://arxiv.org/abs/2109.07581","arxiv_id":"2109.07581","title":"The Impact of COVID-19 on Sports Betting Markets","body_source":"marker","body_length":51304,"parse_seconds":69.73,"failure_reason":null,"rejected":false,"exit_code":0,"marker_ready":true,"total_seconds":69.86,"processed_at":"2026-05-08T15:53:43.927252+00:00","attempt":1,"queue_status":"done"}
{"candidate_id":"arxiv:1910.08858","source_url":"https://arxiv.org/abs/1910.08858","arxiv_id":"1910.08858","title":"Beating the House: Identifying Inefficiencies in Sports Betting Markets","body_source":"marker","body_length":60645,"parse_seconds":48.31,"failure_reason":null,"rejected":false,"exit_code":0,"marker_ready":true,"total_seconds":48.53,"processed_at":"2026-05-08T15:54:32.519493+00:00","attempt":1,"queue_status":"done"}
```

### `Select-String results.jsonl -Pattern "ipc_warm_worker_used"`

Exit code: 0

```text

```

No match. The persisted results artifact omits `ipc_warm_worker_used`.

### `Select-String daemon_fix_direct_pdf_live_20260508_115111.log -Pattern "ipc_warm_worker_used|body_source|parse_seconds|daemonic|pdfplumber|Traceback|Exception|error"`

Exit code: 0

```text
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:8:      "body_source": "marker",
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:10:      "parse_seconds": 45.55,
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:19:      "ipc_warm_worker_used": true
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:26:      "body_source": "marker",
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:28:      "parse_seconds": 69.73,
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:37:      "ipc_warm_worker_used": true
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:44:      "body_source": "marker",
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:46:      "parse_seconds": 48.31,
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:55:      "ipc_warm_worker_used": true
artifacts\research\marker_ipc_validation\daemon_fix_direct_pdf_live_20260508_115111.log:59:  "ipc_warm_worker_used": true
```

### `rg -n "daemon=False|def start|def restart|_make_process|process_next_ipc|fetch_pdf_direct|pdf_url|ipc_warm_worker_used|body_source" ...`

Exit code: 0. Relevant matches:

```text
packages\research\ingestion\marker_ipc_worker.py:239:    def _make_process(self, target, args, daemon=False):
packages\research\ingestion\marker_ipc_worker.py:266:    def start(self) -> None:
packages\research\ingestion\marker_ipc_worker.py:287:        # daemon=False is required: daemon processes cannot spawn child processes,
packages\research\ingestion\marker_ipc_worker.py:292:        proc = self._make_process(
packages\research\ingestion\marker_ipc_worker.py:295:            daemon=False,
packages\research\ingestion\marker_ipc_worker.py:404:    def restart(self) -> None:
packages\research\ingestion\marker_queue.py:337:    def process_next_ipc(
packages\research\ingestion\marker_queue.py:369:        list of result dicts, each containing ``ipc_warm_worker_used`` bool.
packages\research\ingestion\marker_queue.py:424:                r["ipc_warm_worker_used"] = ipc_used
packages\research\ingestion\marker_queue.py:458:            pdf_url = item.get("pdf_url", "")
packages\research\ingestion\marker_queue.py:459:            if pdf_url and hasattr(fetcher, "fetch_pdf_direct"):
packages\research\ingestion\marker_queue.py:460:                raw = fetcher.fetch_pdf_direct(pdf_url, title=item.get("title", ""))
packages\research\ingestion\fetchers.py:672:    def fetch_pdf_direct(self, url_or_path: str, title: str = "") -> dict:
tools\cli\research_marker_queue.py:199:    results = q.process_next_ipc(max_items=max_items, marker_timeout=marker_timeout)
tools\cli\research_marker_queue.py:202:        any_ipc = any(r.get("ipc_warm_worker_used") for r in results)
tools\cli\research_marker_queue.py:206:            "ipc_warm_worker_used": any_ipc,
tools\cli\research_marker_queue.py:307:        dest="pdf_url",
```

### `rg` L1-blocked scan over current docs

Exit code: 0 for the properly quoted Obsidian paths. Relevant output:

```text
docs/obsidian-vault/Claude Desktop/Current-Focus.md:20:- ~~**Academic pipeline hosting**~~ -- **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). Hosting blocker resolved; L1 remains blocked by Marker Docker IPC warm-worker validation (>=3 warm papers, <=10s/paper for papers 2+) -- see 2026-05-07 live validation dev log.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:29:| L1 | [[Work-Packet - Marker Structural Parser Integration]] | **BLOCKED -- awaiting Docker IPC warm-worker (v1).** Queue v0 shipped 2026-05-05 (queue, CLI, indexing gate, failure semantics, 43 tests). Docker IPC warm-worker deferred to v1. L1 production Marker rollout remains blocked until v1 IPC warm-worker validates >=3 papers warm (<=10s/paper for papers 2+). pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:56:- **2026-05-03**: Academic pipeline hosting decision accepted. Docker GPU passthrough verified (RTX 2070 Super, CUDA 13.2, `docker run --gpus all` succeeds). Q1->B (Docker+GPU dev machine), Q2->confirmed, Q3->moot, Q4->academic on dev / others on partner, Q5->volume-mount host cache. ~~L1 Marker production rollout unblocked.~~ *(stale -- hosting blocker resolved but L1 re-blocked: Docker IPC warm-worker live validation failed 2026-05-07; L1 remains blocked pending >=3 warm papers at <=10s/paper.)* Next packet: [[Work-Packet - Marker Structural Parser Integration]]. Dev log: `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`.
```

---

## Decisions

- Feature 3 live validation FAILS under the current acceptance gate.
- Feature 3 closeout may NOT run next.
- L1 Marker production rollout remains blocked.
- The daemon=False fix itself is validated functionally.
- No retry should run unless the operator changes the timing gate or approves a new paper set.

---

## Blockers / Fixes

Blocking:

- Papers 2 and 3 exceed <=10s: 69.73s and 48.31s.

Non-blocking but important artifact caveat:

- `ipc_warm_worker_used=true` is present in the live command JSON output, but absent from
  persisted `results.jsonl`. If closeout criteria require this field in queue result
  artifacts, set it before `_append_result()` in `MarkerParseQueue.process_next_ipc()`
  or persist an equivalent warm-worker provenance field.

Operator decision needed:

- Revise the warm-paper timing gate, choose simpler validation papers and approve a new
  one-attempt validation, or keep Feature 3 blocked.

---

## Codex Review Summary

Tier: read-only verification review of research ingestion/queue live validation artifacts.
Mandatory trading, execution, kill-switch, risk-manager, rate-limiter, SVM, L2, and L4
code were not in scope.

Issues found: one blocking Feature 3 live-gate failure (papers 2+ over <=10s). One
artifact caveat (`ipc_warm_worker_used` not persisted in `results.jsonl`).

Issues addressed: none. Per instruction, no code, queue, Docker, test, SVM, trading, L2,
or L4 changes were made. Only this dev log was created.
