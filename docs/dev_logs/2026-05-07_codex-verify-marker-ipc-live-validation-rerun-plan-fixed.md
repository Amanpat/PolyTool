# Codex Verify: Marker IPC Live-Validation Rerun Plan Fixed

Date: 2026-05-07
Type: read-only verification review
Scope: review-only. This dev log is the only file created by Codex in this pass.
Verdict: PASS

## Objective

Verify the corrected Marker IPC live-validation rerun plan and decide whether a
second live Docker validation attempt may be planned next.

## Decision

PASS. A second live Docker validation attempt may be planned next, but it may
NOT be executed immediately.

The corrected plan is now safe as a planning artifact because it blocks live
validation until all five preflight items are checked with evidence:

1. arXiv API cooldown/pre-check passes.
2. papers 2-3 are selected and visually verified by the operator.
3. Docker image rebuild exits 0.
4. fresh isolated validation queue is created with 3 verified papers.
5. validation queue counts show exactly `pending=3`, `failed=0`, `total=3`.

L1 remains blocked until the live Docker/GPU run itself passes all gates.

## Verification Checklist

| Check | Result | Notes |
|---|---|---|
| 1. All enqueue commands include required `--url` and match CLI help/source | PASS | `enqueue --help` requires `--url URL_OR_ID`; all plan enqueue call sites include `--url`. |
| 2. Plan does not mark Docker build, queue reset, candidate verification, or counts complete without evidence | PASS | Preflight checklist uses unchecked `[ ]` items and explicitly requires evidence before rerun. |
| 3. Candidate set is either verified or blocks live validation until candidate selection is completed | PASS | Candidate set is not fully verified, but the plan explicitly blocks live validation until operator verifies papers 2-3. |
| 4. Plan avoids relying on risky/unknown papers as required validation candidates | PASS | `2412.14173` is excluded; `2204.05149` is marked unverified; Step 2 uses placeholders in a fresh queue. |
| 5. Plan includes stop condition for arXiv 429/API timeout | PASS | Step 3 and Guardrails require immediate stop on Paper 1 429/timeout. |
| 6. Plan preserves gates: >=3 completed papers, papers 2+ <=10s, IPC flag true, no fallback, clean shutdown | PASS | G1-G6 and pass criteria cover 3 papers, <=10s warm papers, `ipc_warm_worker_used=true`, Marker-only body source, and no orphan subprocesses. |
| 7. L1 remains blocked; no premature closeout/unblock language | PASS | Plan header/footer state BLOCKED. Any "unblocked" language is conditional on all gates passing, not a current closeout. |
| 8. No code/tests/Docker/artifacts/queue/SVM/trading/L2/L4 changes occurred during plan fix | PASS WITH NOTE | Current tracked diff still contains earlier Marker IPC code/test/Docker changes from the prior fix set, matching the previous review log. The plan-fix dev log scopes the fix to the rerun plan plus its dev log, and states no code, tests, Docker, queue, or warm-process runs occurred. No validation queue artifact exists and no `warm_process_rerun_*` log is present. |

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md`
- `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md`
- `docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md`
- `tools/cli/research_marker_queue.py`
- `packages/research/ingestion/marker_queue.py`

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
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md
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

Exit code: 0. CLI loaded successfully and `research-marker-queue` is present.

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

Warnings emitted:

```text
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
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

Warnings emitted:

```text
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
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

### `python -m polytool research-marker-queue counts --help`

Exit code: 0

```text
usage: polytool research-marker-queue counts [-h] [--json]

options:
  -h, --help  show this help message and exit
  --json      Output counts as JSON
```

### Targeted plan checks

Command:

```powershell
$lines = Get-Content docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md; for ($i=0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match 'research-marker-queue.*enqueue' -and $lines[$i] -notmatch '--url') { '{0}:{1}' -f ($i+1), $lines[$i] } }
```

Exit code: 0

```text
```

No enqueue call site was found without `--url`.

Command:

```powershell
Select-String -Path docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md -Pattern '\[x\]'
```

Exit code: 0

```text
```

No checked preflight item was found.

Command:

```powershell
Select-String -Path docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md,docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md -Pattern 'SVM','trading','L2','L4','PaperQA2','live capital','Gate 2','benchmark'
```

Exit code: 0

```text
```

No SVM/trading/L2/L4/Gate 2/baseline scope was found in the corrected rerun
plan or its fix dev log.

### Artifact / queue read-only checks

Command:

```powershell
if (Test-Path artifacts/research/marker_validation_queue) { Get-ChildItem artifacts/research/marker_validation_queue -Force | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 200 } else { 'MISSING artifacts/research/marker_validation_queue' }
```

Exit code: 0

```text
MISSING artifacts/research/marker_validation_queue
```

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

## Fixes Required

None for the corrected rerun plan.

## What Remains Blocked

Live validation itself remains blocked until the five preflight items in the
plan are completed with evidence. The immediate next non-Docker planning step is
candidate selection for papers 2-3.

## Codex Review Summary

Tier: skip/read-only validation review. No code, tests, Docker, queue,
artifacts, SVM, trading, L2, or L4 files were changed by Codex in this pass.

Issues found: none requiring changes to the corrected rerun plan.

Issues addressed: none. Per instruction, only this review dev log was created.
