---
title: Codex Verify Marker Docker Ipc Warm Worker Live Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify Marker Docker IPC Warm-Worker Live Validation

Date: 2026-05-07
Type: read-only validation review
Scope: review-only. This dev log is the only file created by Codex.
Verdict: FAIL

## Objective

Verify whether the Marker Docker IPC warm-worker v1 live validation satisfies
Feature 3 acceptance gates and whether closeout prompts may run next.

## Decision

FAIL. Feature 3 acceptance gates are not met. Closeout prompts may NOT run next.

The live Docker/GPU path was exercised and the IPC worker route was used, but no
paper completed successfully. The required evidence for one warm-worker session
processing at least three papers, with papers 2+ at <=10s each, does not exist.

There is also a documentation blocker: current/navigation docs still contain
stale "L1 Marker production rollout unblocked" claims in `docs/INDEX.md` and
`docs/obsidian-vault/Claude Desktop/Current-Focus.md`. Authoritative current
development and validation logs state L1 remains blocked, but the stale claims
violate the review gate until corrected.

## Files and Artifacts Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md`
- `docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md`
- `artifacts/research/marker_ipc_validation/warm_process_20260507.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run2.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run3.log`
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run4.log`
- `artifacts/research/marker_parse_queue/results.jsonl`

## Gate Verdicts

| Gate | Result | Evidence |
|---|---|---|
| 1. Live validation ran inside Docker/Linux/GPU target | PASS | Validation log records WSL2 Docker engine, RTX 2070 SUPER, CUDA 13.2, host `nvidia-smi`, and GPU OCR progress in runs 2 and 3. |
| 2. One warm-worker session processed >=3 papers | FAIL | Zero papers completed in any run. Run 1 hit stale extractor TypeError, run 2 timed out on paper 1, run 3 was aborted, run 4 was blocked by arXiv API timeout/429. |
| 3. Papers 2+ parse at <=10s/paper | NOT TESTED / FAILING ACCEPTANCE | Paper 1 never completed, so no paper 2+ warm parse timing exists. |
| 4. `ipc_warm_worker_used=true` appears for live results | PARTIAL PASS | The warm-process JSON logs include `ipc_warm_worker_used: true` on processed attempt records and run-level output. Final `results.jsonl` records from run 4 omit the field because fetch failed before a parse was attempted. There are no successful live parse results. |
| 5. No pdfplumber fallback occurred | PASS | Artifact logs and queue results show `body_source` values of `marker_failed` or `error`; no `pdfplumber` result appears. |
| 6. Queue v0 semantics remained intact | PASS | Queue counts are `pending=2, processing=0, done=0, failed=1, total=3`; result records show retry attempts and failed terminal status for max retries. |
| 7. Worker shutdown clean / no orphan subprocesses | PASS WITH CAVEAT | Validation log reports only 6 processes after runs and the validation container was stopped/removed. Current `docker ps` shows no `ris-gpu-validation` container. Caveat: run 2 emitted a multiprocessing leaked semaphore warning. |
| 8. No implementation/tests/config/Docker/SVM/trading files changed during validation | PASS WITH CAVEAT | Current implementation/test dirty state matches the validation baseline. No config, infra, Docker, artifacts, SVM, or trading paths are modified. The repo remains dirty from pre-existing implementation work. |
| 9. L2/PaperQA2 and L4 remain blocked/stubbed | PASS | Work packet states L2 PaperQA2 remains stubbed and L4 harvesters remain stubbed; Current-Focus also lists L2 and L4 as stubs. |
| 10. Docs do not claim L1 production unblocked unless review passes | FAIL | `docs/INDEX.md:181`, `Current-Focus.md:20`, and `Current-Focus.md:56` still contain stale unblocked claims. |

Overall: FAIL.

## Per-Paper / Per-Attempt Timings

No paper completed successfully. These are the observed timings from the live
validation artifacts.

| Run | Candidate | Attempt | parse_seconds | total_seconds | Outcome | IPC flag |
|---|---:|---:|---:|---:|---|---|
| 1 | arxiv:2310.06825 | 1 | 0.0 | 52.1 | `marker model load failed: MarkerPDFExtractor.__init__() got an unexpected keyword argument '_preloaded_model_dict'` | true |
| 1 | arxiv:2310.06825 | 2 | 900.05 | 900.56 | `marker_timeout: extraction timed out after 900.0s` | true |
| 1 | arxiv:2310.06825 | 3 | 0.0 | 0.63 | `worker_not_running: call start() before parse()` | true |
| 2 | arxiv:2310.06825 | 1 | 900.07 | 901.09 | `marker_timeout: extraction timed out after 900.0s` | true |
| 2 | arxiv:2310.06825 | 2 | 0.0 | 0.55 | `worker_not_running: call start() before parse()` | true |
| 2 | arxiv:2310.06825 | 3 | 0.0 | 0.50 | `worker_not_running: call start() before parse()` | true |
| 2 | arxiv:2005.11401 | 1 | 0.0 | 0.23 | HTTP 429 from arXiv metadata API | true |
| 2 | arxiv:2005.11401 | 2 | 0.0 | 15.11 | Timeout fetching arXiv metadata API | true |
| 3 | arxiv:2104.08691 | n/a | n/a | n/a | Aborted after OCR reached 43/139 chunks; no JSON result / no parse_seconds | n/a |
| 4 | arxiv:2604.24366 | 1 | 0.0 | 15.12 | Timeout fetching arXiv metadata API | true in run output; absent from `results.jsonl` |
| 4 | arxiv:2604.24366 | 2 | 0.0 | 15.07 | Timeout fetching arXiv metadata API | true in run output; absent from `results.jsonl` |
| 4 | arxiv:2604.24366 | 3 | 0.0 | 15.06 | Timeout fetching arXiv metadata API | true in run output; absent from `results.jsonl` |
| 4 | arxiv:2412.14173 | 1 | 0.0 | 0.19 | HTTP 429 from arXiv metadata API | true in run output; absent from `results.jsonl` |
| 4 | arxiv:2412.14173 | 2 | 0.0 | 0.18 | HTTP 429 from arXiv metadata API | true in run output; absent from `results.jsonl` |

## Blockers / Fixes Before Retest

1. Fix or work around arXiv metadata API rate limiting. The live fetch path
   calls arXiv metadata before PDF download and cannot currently bypass that
   when metadata is pre-known.
2. Use simple text-heavy papers for validation. The Mistral and LoRA papers
   were too complex for the 900s timeout on this hardware.
3. Fix worker restart after timeout. After a timeout kills the IPC worker,
   later attempts in the same `warm-process` call return `worker_not_running`.
4. Fix Docker image rebuild. `Dockerfile.ris` needs the
   `packages/research/relevance_filter` stub directory during build.
5. Investigate the run 2 leaked semaphore warning before production use.
6. Remove stale L1-unblocked claims from `docs/INDEX.md` and
   `docs/obsidian-vault/Claude Desktop/Current-Focus.md`.

## Commands Run and Outputs

### `git status --short`

Exit code: 0

```text
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

After this dev log is written, it will also appear as untracked.

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

CLI loaded successfully. The output included `research-marker-queue` under RIS
commands.

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

### `python -m polytool research-marker-queue counts --json`

Exit code: 0

```json
{
  "pending": 2,
  "processing": 0,
  "done": 0,
  "failed": 1,
  "total": 3
}
```

### `docker ps`

Exit code: 0

```text
CONTAINER ID   IMAGE                                 COMMAND                  CREATED      STATUS                 PORTS                                                                                      NAMES
7096c85085a0   polytool-ris-scheduler                "python -m polytool ..."   2 days ago   Up 2 hours                                                                                                        polytool-ris-scheduler
a421e931d2ef   clickhouse/clickhouse-server:latest   "/entrypoint.sh"         2 days ago   Up 2 hours (healthy)   0.0.0.0:8123->8123/tcp, [::]:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp   polytool-clickhouse
```

No `ris-gpu-validation` container remained running.

### Host process check

Command:

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'marker|surya|python' } | Select-Object Id,ProcessName,Path | Format-Table -AutoSize | Out-String -Width 240
```

Exit code: 0

```text
   Id ProcessName Path
   -- ----------- ----
10132 python      C:\Users\patel\AppData\Local\Programs\Python\Python313\python.exe
14980 python      C:\Users\patel\AppData\Local\Programs\Python\Python313\python.exe
17764 python      C:\Users\patel\pipx\venvs\code-review-graph\Scripts\python.exe
21228 python      C:\Users\patel\AppData\Local\Programs\Python\Python313\python.exe
22104 python      D:\Coding Projects\Polymarket\PolyTool\.venv\Scripts\python.exe
27304 python      C:\Users\patel\AppData\Local\uv\cache\archive-v0\W1Gz2pXkeVAPgqFfoSXpJ\Scripts\python.exe
29608 python      C:\Users\patel\AppData\Local\Programs\Python\Python313\python.exe
31212 python      C:\Users\patel\pipx\venvs\code-review-graph\Scripts\python.exe
```

No host process named Marker or Surya was found by this check.

### Scoped status check

Command:

```powershell
git status --short -- packages tools tests config infra docker-compose.yml Dockerfile.ris artifacts docs/INDEX.md 'docs/obsidian-vault/Claude Desktop/Current-Focus.md' docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md
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

### Scoped diff check

Command:

```powershell
git diff --name-status -- packages tools tests config infra docker-compose.yml Dockerfile.ris artifacts docs/INDEX.md 'docs/obsidian-vault/Claude Desktop/Current-Focus.md' docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md
```

Exit code: 0

```text
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### Artifact file listing

Command:

```powershell
if (Test-Path artifacts/research/marker_ipc_validation) { Get-ChildItem -Recurse -File artifacts/research/marker_ipc_validation | Select-Object FullName,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 240 } else { 'MISSING artifacts/research/marker_ipc_validation' }
```

Exit code: 0

```text
FullName                                                                                                       Length LastWriteTime
--------                                                                                                       ------ -------------
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log        1988 5/7/2026 11:56:34 AM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log   6583 5/7/2026 12:16:30 PM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run3.log   3246 5/7/2026 12:37:40 PM
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run4.log   3265 5/7/2026 12:42:18 PM
```

### Stale L1-unblocked claim search

Command:

```powershell
Select-String -Path 'docs/INDEX.md','docs/obsidian-vault/Claude Desktop/Current-Focus.md','docs/CURRENT_DEVELOPMENT.md','docs/CURRENT_STATE.md' -Pattern 'L1 Marker production rollout unblocked','L1 Marker production rollout is now unblocked','L1 is unblocked','production rollout unblocked' -CaseSensitive:$false | ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line)" }
```

Exit code: 0

```text
D:\Coding Projects\Polymarket\PolyTool\docs\INDEX.md:181:| [Academic Pipeline Hosting Decision](dev_logs/2026-05-03_academic-pipeline-hosting-decision.md) | 2026-05-03 | Hosting decision accepted: Docker+GPU dev machine, passthrough verified (RTX 2070 Super, CUDA 13.2), volume-mount weights, hard-cutover rollout; L1 Marker production rollout unblocked |
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\Current-Focus.md:20:- ~~**Academic pipeline hosting**~~ - **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). L1 Marker production rollout is now unblocked.
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\Current-Focus.md:56:- **2026-05-03**: Academic pipeline hosting decision accepted. Docker GPU passthrough verified (RTX 2070 Super, CUDA 13.2, `docker run --gpus all` succeeds). Q1->B (Docker+GPU dev machine), Q2->confirmed, Q3->moot, Q4->academic on dev / others on partner, Q5->volume-mount host cache. L1 Marker production rollout unblocked. Next packet: [[Work-Packet - Marker Structural Parser Integration]]. Dev log: `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`.
```

### L2/L4 blocked/stubbed check

Command:

```powershell
Select-String -Path 'docs/CURRENT_DEVELOPMENT.md','docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md','docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md','docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md' -Pattern 'L2 PaperQA2','L4','stub','blocked','No L2','No L4' -CaseSensitive:$false | ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line)" }
```

Exit code: 0

Key output:

```text
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:15:  - "[[Work-Packet - PaperQA2 RAG Control Flow]] - L2 explicitly blocked until warm-worker acceptance gates pass"
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:24:> **L2 PaperQA2 RAG Control Flow is BLOCKED until Feature 3 passes.**
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:76:**L2 gate:** L2 PaperQA2 RAG Control Flow remains stub and does NOT activate until gates 1-7 above are all satisfied and the acceptance dev log is written.
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:82:- **No L2 work.** `Work-Packet - PaperQA2 RAG Control Flow` remains stub. L2 activation gates on warm-worker passing.
D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:83:- **No L4 work.** Multi-source academic harvesters remain stub and are not touched.
```

### Artifact grep for pdfplumber / IPC / failure markers

`rg` failed in this shell with `Access is denied`, so PowerShell
`Select-String` was used instead.

Command:

```powershell
$paths = @(); if (Test-Path artifacts/research/marker_ipc_validation) { $paths += Get-ChildItem artifacts/research/marker_ipc_validation -File | ForEach-Object { $_.FullName } }; if (Test-Path artifacts/research/marker_parse_queue/results.jsonl) { $paths += 'artifacts/research/marker_parse_queue/results.jsonl' }; Select-String -Path $paths -Pattern 'pdfplumber','body_source','ipc_warm_worker_used','marker_failed','worker_not_running','marker_timeout' -CaseSensitive:$false | ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line)" }
```

Exit code: 0

Relevant output:

```text
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log:9:      "body_source": "marker_failed",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log:20:      "ipc_warm_worker_used": true
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log:30:      "failure_reason": "marker_timeout: extraction timed out after 900.0s",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507.log:48:      "failure_reason": "worker_not_running: call start() before parse()",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log:53:      "body_source": "marker_failed",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log:56:      "failure_reason": "marker_timeout: extraction timed out after 900.0s",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run2.log:64:      "ipc_warm_worker_used": true
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run4.log:8:      "body_source": "error",
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_ipc_validation\warm_process_20260507_run4.log:19:      "ipc_warm_worker_used": true
D:\Coding Projects\Polymarket\PolyTool\artifacts\research\marker_parse_queue\results.jsonl:1:{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market","body_source":"error","body_length":0,"parse_seconds":0.0,"failure_reason":"Timeout fetching http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1","rejected":true,"exit_code":1,"marker_ready":false,"total_seconds":15.12,"processed_at":"2026-05-07T16:41:46.569826+00:00","attempt":1,"queue_status":"pending"}
```

No `pdfplumber` hit appeared in artifact/result output.

## Codex Review Summary

Tier: Skip / read-only validation evidence review. This did not review trading
execution, risk, SVM implementation, or live-capital files.

Issues found: live acceptance FAIL; stale L1-unblocked doc claims remain; worker
restart-after-timeout, Dockerfile rebuild, arXiv rate limiting, complex-paper
timeout, and semaphore cleanup remain blockers.

Issues addressed: none. Per instruction, no code, config, artifact, Docker, SVM,
trading, or existing docs were edited. This dev log is the only change.
