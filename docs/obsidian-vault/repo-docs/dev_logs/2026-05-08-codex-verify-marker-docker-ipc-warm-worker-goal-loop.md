---
title: Codex Verify Marker Docker Ipc Warm Worker Goal Loop
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-goal-loop.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify - Marker Docker IPC Warm-Worker Goal Loop

Date: 2026-05-08
Type: read-only goal-loop verification
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1
Verdict: **FAIL for Feature 3 completion**

## Summary

Feature 3 is **not complete**. The latest validation run did not satisfy the
warm-worker acceptance gate: only one paper completed, papers 2+ did not reach
Marker parsing, and no evidence exists that papers 2+ parse at <=10s in one
warm Docker/Linux/GPU session.

The failure evidence and next blocker are documented in the latest validation
log, but the "no code/Docker changes" check cannot be cleanly confirmed from
the current working tree: `Dockerfile.ris` and Marker queue/IPC code paths are
modified or untracked. No SVM, trading, L2/PaperQA2, or L4 code changes were
found in the scoped checks.

Review output file is the only file changed by this Codex verification pass.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md`
- `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md`
- `artifacts/research/marker_ipc_validation/validation_run.json`
- `artifacts/research/marker_validation_queue/queue.jsonl`
- `artifacts/research/marker_validation_queue/results.jsonl`

## Decision

**FAIL. Feature 3 is still blocked.**

The latest live validation is a partial technical improvement over the
2026-05-07 failure because paper 1 completed through IPC with
`body_source=marker`, `parse_seconds=39.19`, and `ipc_warm_worker_used=true`.
That still does not satisfy the acceptance gate requiring >=3 papers in one
session and <=10s parses for papers 2+.

The next blocker is specific: paper 2 (`arxiv:1910.08858`) failed before Marker
parsing due to arXiv metadata API timeout followed by HTTP 429. Paper 3
(`arxiv:2109.07581`) was never attempted because the `--max-items=3` budget was
consumed by paper 1 plus two paper-2 attempts.

## Gate-By-Gate Verdict

| Gate | Status | Evidence |
|---|---|---|
| Determine validation pass/fail | **FAIL** | Latest run processed only one successful paper; papers 2+ have no warm parse timings. |
| No closeout happened | **PASS** | No `*marker-docker-ipc-warm-worker*v1-closeout*` log found; no `docs/features/*marker*ipc*` feature doc exists; latest validation log says closeout protocol was not executed. |
| Gate-by-gate failure evidence exists | **PASS** | Latest validation log has a gate table and raw JSON artifact has exact paper outcomes. |
| No code/Docker/SVM/trading/L2/L4 changes occurred | **FAIL / MIXED** | Current working tree has code and Docker changes (`Dockerfile.ris`, Marker queue/IPC code/tests/CLI). Scoped checks found no SVM, trading, L2, or L4 code changes. |
| Next blocker is specific | **PASS** | arXiv metadata API timeout/429 on paper 2; next actions are cooldown retry or local-cache/prestaged-paper path. |
| One live Docker/Linux/GPU session processed >=3 papers | **FAIL** | Queue counts are `done=1`, `pending=2`, `failed=0`; paper 3 untouched. |
| Papers 2+ each parse at <=10s | **FAIL / NOT TESTED** | Papers 2+ did not reach Marker parsing; parse seconds are `0.0` error attempts. |
| `ipc_warm_worker_used=true` | **PARTIAL PASS** | Present in `validation_run.json` for all processed entries and run-level output. Not present in `results.jsonl` records. |
| Body source is Marker; no pdfplumber fallback | **PARTIAL PASS** | Successful paper has `body_source=marker`; failed attempts have `body_source=error`; no `pdfplumber` result found. |
| Clean shutdown / no orphan process check | **PASS for current Docker state** | `docker ps --all` showed no containers. |
| Completion protocol | **NOT EXECUTED** | No feature doc, no v1 closeout log, and `CURRENT_DEVELOPMENT.md` did not move Marker Docker IPC warm-worker v1 to Recently Completed. |
| L2/PaperQA2/L4 were not started | **PASS** | Docs still say L2 and L4 are stubs/blocked; file search found only existing work-packet notes. |
| Docs avoid full mature academic RAG overclaim | **PASS** | Current focus says L1 is blocked, L2/L4 are stubs. No "full mature academic RAG complete" claim found in checked docs. |
| Low-disk risk recorded | **PASS** | Prior 2026-05-08 log records C drive at 2.05GB before and 1.87GB after failed image attempt; latest log records 65.22GB after operator freed space. |

## Per-Paper Timing Table

From `artifacts/research/marker_ipc_validation/validation_run.json`:

| Paper | arXiv ID | Attempt | parse_seconds | total_seconds | body_source | ipc_warm_worker_used | Outcome |
|---|---|---:|---:|---:|---|---|---|
| 1 | 2604.24366 | 1 | 39.19 | 179.91 | marker | true | PASS for single-paper IPC parse |
| 2 | 1910.08858 | 1 | 0.0 | 15.11 | error | true | FAIL - arXiv metadata timeout |
| 2 | 1910.08858 | 2 | 0.0 | 0.81 | error | true | FAIL - arXiv HTTP 429 |
| 3 | 2109.07581 | n/a | n/a | n/a | n/a | n/a | NOT RUN |

## Completion Protocol Status

Closeout did not happen, which is correct for the failed validation.

| Completion item | Status |
|---|---|
| Feature doc created | NOT DONE; no `docs/features/*marker*ipc*` result. |
| INDEX updated for v1 closeout | NOT DONE; no v1 feature closeout row found. |
| CURRENT_DEVELOPMENT moved Feature 3 to Recently Completed | NOT DONE; no v1 Recently Completed entry. |

## Current Feature Status

Feature 3 remains blocked. The latest concrete retry state:

- Paper 1 (`2604.24366`) is `done`, attempts=1.
- Paper 2 (`1910.08858`) is `pending`, attempts=2, blocked by arXiv timeout/429.
- Paper 3 (`2109.07581`) is `pending`, attempts=0.

## Fixes Required Before Closeout

1. Re-run validation after arXiv cooldown, or use a local-cache/prestaged-paper
   path that avoids live arXiv metadata API calls during warm-process validation.
2. Ensure the validation run processes at least three unique papers in one
   Docker/Linux/GPU warm-worker session.
3. Capture papers 2+ with `parse_seconds <=10s`.
4. Preserve `body_source=marker`, no pdfplumber fallback, and clean worker
   shutdown evidence.
5. Resolve or explicitly baseline the current code/Docker dirty tree before
   any future claim that no code/Docker changes occurred.
6. Only after passing validation, execute completion protocol: feature doc,
   INDEX update, and CURRENT_DEVELOPMENT move to Recently Completed.

## Commands Run And Outputs

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
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
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

Exit code: 0

```text
CLI loaded successfully. Output included the RIS command `research-marker-queue`.
```

### `git diff --stat`

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  97 +++------
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 ++++++++++--------
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  31 +--
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            |  66 ++++++
 packages/research/ingestion/marker_queue.py        |  98 +++++++++
 tests/test_ris_marker_queue.py                     | 236 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 114 ++++++++++
 13 files changed, 700 insertions(+), 179 deletions(-)
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### Latest validation logs

Command:

```powershell
Get-ChildItem -Path docs/dev_logs -Filter '*marker-docker-ipc-warm-worker*validation*' | Sort-Object LastWriteTime -Descending | Select-Object -First 10 -Property LastWriteTime,Name
```

Exit code: 0

```text
LastWriteTime        Name
-------------        ----
5/8/2026 9:50:55 AM  2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
5/8/2026 9:25:12 AM  2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
5/7/2026 1:14:59 PM  2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md
5/7/2026 12:55:17 PM 2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
```

Command:

```powershell
Get-ChildItem -Path docs/dev_logs -Filter '*marker-docker-ipc-warm-worker*v1-closeout*' | Sort-Object LastWriteTime -Descending | Select-Object -First 10 -Property LastWriteTime,Name
```

Exit code: 0

```text
<no output>
```

### Artifact listing

Command:

```powershell
Get-ChildItem -Recurse -File artifacts/research/marker_ipc_validation | Select-Object FullName,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 240
```

Exit code: 0

```text
FullName                                                                                                       Length LastWriteTime
--------                                                                                                       ------ -------------
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\validation_run.json              4264 5/8/2026 9:48:15 AM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log        1988 5/7/2026 11:56:34 AM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log   6583 5/7/2026 12:16:30 PM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run3.log   3246 5/7/2026 12:37:40 PM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run4.log   3265 5/7/2026 12:42:18 PM
```

Command:

```powershell
Get-ChildItem -Recurse -File artifacts/research/marker_validation_queue | Select-Object FullName,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 240
```

Exit code: 0

```text
FullName                                                                                        Length LastWriteTime
--------                                                                                        ------ -------------
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_validation_queue\queue.jsonl      961 5/8/2026 9:48:13 AM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_validation_queue\results.jsonl   1499 5/8/2026 9:48:13 AM
```

### Queue counts/list

Command:

```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue counts --json
```

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

Command:

```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue list
```

Exit code: 0

```text
  candidate_id                 status       att   title
  -------------------------------------------------------------------------------------------
  arxiv:2604.24366             done         1     The Anatomy of a Decentralized Predictio
  arxiv:1910.08858             pending      2     Beating the House: Identifying Inefficie
  arxiv:2109.07581             pending      0     The Impact of COVID-19 on Sports Betting

Total: 3 item(s)
```

### Validation JSON

Command:

```powershell
Get-Content -Raw artifacts/research/marker_ipc_validation/validation_run.json
```

Exit code: 0

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
      "parse_seconds": 39.19,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 179.91,
      "processed_at": "2026-05-08T13:47:57.171881+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "source_url": "https://arxiv.org/abs/1910.08858",
      "arxiv_id": "1910.08858",
      "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
      "body_source": "error",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "Timeout fetching http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 15.11,
      "processed_at": "2026-05-08T13:48:12.323443+00:00",
      "attempt": 1,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "source_url": "https://arxiv.org/abs/1910.08858",
      "arxiv_id": "1910.08858",
      "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
      "body_source": "error",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "HTTP 429 Unknown Error for http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.81,
      "processed_at": "2026-05-08T13:48:13.151436+00:00",
      "attempt": 2,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

### Queue results

Command:

```powershell
Get-Content -Raw artifacts/research/marker_validation_queue/results.jsonl
```

Exit code: 0

```json
{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book","body_source":"marker","body_length":56923,"parse_seconds":39.19,"failure_reason":null,"rejected":false,"exit_code":0,"marker_ready":true,"total_seconds":179.91,"processed_at":"2026-05-08T13:47:57.171881+00:00","attempt":1,"queue_status":"done"}
{"candidate_id":"arxiv:1910.08858","source_url":"https://arxiv.org/abs/1910.08858","arxiv_id":"1910.08858","title":"Beating the House: Identifying Inefficiencies in Sports Betting Markets","body_source":"error","body_length":0,"parse_seconds":0.0,"failure_reason":"Timeout fetching http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1","rejected":true,"exit_code":1,"marker_ready":false,"total_seconds":15.11,"processed_at":"2026-05-08T13:48:12.323443+00:00","attempt":1,"queue_status":"pending"}
{"candidate_id":"arxiv:1910.08858","source_url":"https://arxiv.org/abs/1910.08858","arxiv_id":"1910.08858","title":"Beating the House: Identifying Inefficiencies in Sports Betting Markets","body_source":"error","body_length":0,"parse_seconds":0.0,"failure_reason":"HTTP 429 Unknown Error for http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1","rejected":true,"exit_code":1,"marker_ready":false,"total_seconds":0.81,"processed_at":"2026-05-08T13:48:13.151436+00:00","attempt":2,"queue_status":"pending"}
```

### Docker process check

Command:

```powershell
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Image}}"
```

Exit code: 0

```text
NAMES     STATUS    IMAGE
```

Command:

```powershell
docker ps --all --format "table {{.Names}}`t{{.Status}}`t{{.Image}}"
```

Exit code: 0

```text
NAMES     STATUS    IMAGE
```

### Feature doc / closeout checks

Command:

```powershell
Get-ChildItem -Path docs/features -Filter '*marker*ipc*' | Select-Object Name,LastWriteTime,Length | Format-Table -AutoSize | Out-String -Width 200
```

Exit code: 0

```text
<no output>
```

Command:

```powershell
Select-String -Path docs/CURRENT_DEVELOPMENT.md -Pattern 'Marker Docker IPC','Warm-Worker','Feature 3','Recently Completed','Paused / Deferred' -CaseSensitive:$false | ForEach-Object { "$($_.LineNumber):$($_.Line)" }
```

Exit code: 0

```text
18:   - Move entry to Recently Completed
88:## Recently Completed (rolling 30 days)
94:| Marker Canonical Academic Parse Queue v0                     | 2026-05-05 | RIS      | `docs/features/ris-marker-structural-parser-scaffold.md` - file-backed queue, CLI surface, `is_marker_ready()` gate, Marker-only `IngestPipeline` gate, short-body rejection (retryable/terminal), honest platform docs. 43 tests; Codex re-review PASS. Docker IPC warm-worker deferred to v1. L1 Marker production rollout still blocked on IPC warm-worker. |
110:## Paused / Deferred
114:| RIS Marker Queue - Docker IPC Warm-Worker (v1)         | 2026-05-05     | Queue v0 shipped. v1 (persistent IPC subprocess, Marker models warm across papers on Linux/Docker) deferred pending operator decision on next packet. | Operator chooses Docker IPC warm-worker packet; validates >=3 papers warm (<=10s/paper for papers 2+) |
115:| RIS L1 Marker Production Rollout - Validation          | 2026-05-05     | Operator chose Option A 2026-05-05: async parse queue. Queue v0 complete (Codex re-review PASS). Blocked on Docker IPC warm-worker (v1). pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. | Docker IPC warm-worker (v1) ships; warm worker validates >=3 papers with `parse_seconds <=10s` for papers 2+ |
139:- **RIS Marker Canonical Academic Parse Queue v0 is COMPLETE (2026-05-05).** Queue, CLI surface, `is_marker_ready()` gate, Marker-only academic indexing gate (`IngestPipeline`), short-body rejection, honest platform docs, 43 tests. Codex re-review PASS. Feature doc: `docs/features/ris-marker-structural-parser-scaffold.md`. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. **Docker IPC warm-worker (v1) is deferred** - multi-paper warm-throughput validation may NOT proceed as an L1 acceptance gate until v1 IPC warm-worker ships. Do NOT start L2 until warm-worker validates >=3 papers warm. **L1 Marker Production Rollout remains PAUSED** - blocked on Docker IPC warm-worker v1. Active count is now 2 (Feature 1 + Feature 2) - one Feature 3 slot is available.
144:- **RIS L3 v1 SVM Topic Filter is COMPLETE (2026-05-07).** Default-off integrated; dry-run + hold-review ready; enforce deferred. Director decision: `BAAI/bge-large-en-v1.5` approved as production model. Feature doc at `docs/features/FEATURE-ris-svm-filter-v1.md`. **Active count is now 2 (Features 1 and 2) - one Feature 3 slot is available.** SVM enforce remains hard-blocked at rc=1 pending future Director approval. SPECTER2 path remains unresolved; BGE-large is the declared production model. Marker Docker IPC warm-worker must now be revisited (see Deferred reminder below).
145:- **REMINDER - Marker Docker/Linux IPC Warm-Worker (Option A) is DEFERRED, NOT CANCELED.** Queue v0 shipped 2026-05-05. v1 (persistent IPC subprocess, Marker models warm across papers on Linux/Docker) must be revisited now that L3/SVM stream is complete, or before L2 production launch (whichever comes first). See Paused/Deferred table row "RIS Marker Queue - Docker IPC Warm-Worker (v1)".
```

### Scoped code/Docker/SVM/trading/L2/L4 checks

Command:

```powershell
git diff --name-status -- packages tools tests config infra docker-compose.yml Dockerfile.ris docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
```

Exit code: 0

```text
M	Dockerfile.ris
M	docs/INDEX.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
```

Command:

```powershell
git status --short -- packages/research/relevance_filter tools/cli/research_prefetch_svm_train.py tools/cli/research_prefetch_discover.py tools/cli/research_acquire.py tests/test_ris_svm_filter.py
```

Exit code: 0

```text
<no output>
```

Command:

```powershell
git status --short -- execution packages/polymarket packages/simtrader polytool/simtrader tools/cli/simtrader.py risk_manager.py rate_limiter.py kill_switch.py
```

Exit code: 0

```text
<no output>
```

Command:

```powershell
rg --files | rg -i "paperqa|multi.source|harvester|academic_harvest|l4"
```

Exit code: 0

```text
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - PaperQA2 RAG Control Flow.md
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Multi-source Academic Harvesters.md
```

### Low-disk evidence search

Command:

```powershell
Select-String -Path docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md,docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md,docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md -Pattern 'C drive free','Disk Space','free space','low disk','1 GB','2.05 GB','65.22 GB','1.87 GB','Docker rebuild' -CaseSensitive:$false | ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line)" }
```

Exit code: 0

```text
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md:32:**C drive free:** 65.22 GB (after operator freed space)
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:16:intact (3 pending, 0 done, 0 failed). The constraint prohibiting Docker rebuild
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:27:**C drive free space:**
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:29:C drive free: 2.05 GB
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:101:**C drive free after attempt:** 1.87 GB (still above 1 GB hard stop)
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:137:## Disk Space
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:139:| Point | C Drive Free |
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:141:| Before attempt | 2.05 GB |
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:142:| After attempt | 1.87 GB |
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:144:Remained above the 1 GB hard stop. No Docker prune or rebuild was run.
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:162:The constraint "No Docker rebuild" was in force for this session; this session stopped
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:207:   This was explicitly out of scope for this session (constraint: "No Docker rebuild")
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md:236:5. **Check C drive free space before rebuild** - currently at 1.87 GB.
```

## Codex Review Summary

Tier: Skip / read-only validation review. No trading execution, risk, SVM
implementation, L2/PaperQA2 implementation, or L4 harvester implementation was
reviewed.

Issues found:

- Feature 3 completion FAIL: only 1/3 papers completed; papers 2+ timing gate
  not tested.
- Current working tree prevents a clean "no code/Docker changes" confirmation.
- Failure blocker is specific and documented: arXiv metadata API timeout/429
  before paper 2 could parse.

Issues addressed: none. Per instruction, no code, Docker, SVM, trading, L2, L4,
queue, or existing docs were edited. This review dev log is the only change.
