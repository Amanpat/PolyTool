---
title: Codex Verify Marker Ipc Direct Pdf Validation Ready
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify - Marker IPC Direct-PDF Validation Readiness

Date: 2026-05-08
Type: read-only validation readiness review
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1, direct-PDF/arXiv-bypass path
Verdict: **PASS - one live Docker validation may run next against the fresh direct queue**

## Decision

**PASS.** The fresh isolated direct-PDF queue is ready for exactly one live
Docker/GPU warm-worker validation run.

This does **not** unblock L1 production. L1 remains blocked until the live run
proves at least 3 papers in one warm-worker session, with papers 2+ at
`parse_seconds <= 10s`, `ipc_warm_worker_used=true`, `body_source=marker`, and no
pdfplumber fallback.

## Files Changed

- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md`
  - Added this review log only.

No code, queue artifacts, Docker files, existing docs, or existing artifacts were
edited by this verification pass.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-goal-loop.md`
- `docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md`
- `docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-validation-queue.md`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `artifacts/research/marker_validation_queue_direct/queue.jsonl`

## Verification Matrix

| Check | Verdict | Evidence |
|---|---|---|
| Direct PDF/local PDF validation avoids arXiv metadata API | PASS | `fetch_pdf_direct()` reads/downloads the PDF and calls `_parse_pdf()`; it does not call `export.arxiv.org/api/query`. Tests inject a metadata fetcher that raises if called. |
| Existing arXiv ID behavior is not broken | PASS | Records without `pdf_url` still call `fetch(source_url)`, and `LiveAcademicFetcher.fetch()` still uses the existing Atom API path. Tests cover normal no-`pdf_url` dispatch. |
| Tests cover bypass path and targeted tests pass | PASS | `TestFetchPdfDirect`, `TestEnqueuePdfUrl`, `TestProcessNextDirectPdf`, and `TestCLIPdfUrl`; `146 passed, 1 skipped`. |
| Fresh isolated direct queue exists with 3 pending, 0 done, 0 failed | PASS | `counts --json` returned `pending=3`, `done=0`, `failed=0`, `total=3`; no `results.jsonl` exists. |
| Candidates are suitable enough for warm-worker validation | PASS | Anchor paper previously parsed through IPC; papers 2 and 3 are prose-heavy betting/sports papers from the prior blocked run and failed only before Marker due to Atom API timeout/429. |
| Enqueue syntax is correct and includes required `--url` | PASS | `enqueue --help` shows required `--url`; preparation log uses `--url` plus `--pdf-url` for all 3 records. |
| `warm-process` was not run after the fix | PASS | Fresh direct queue has only `queue.jsonl`, no `results.jsonl`, all records `attempts=0`, and queue-prep log says no live parsing occurred. |
| No Docker rebuild/prune/live Marker job was run | PASS for this review and direct queue prep | I ran no Docker commands. Queue artifacts show no live run. Prior direct-queue prep log records no Docker containers started. |
| No SVM/trading/L2/L4 changes occurred | PASS for code paths, with caveat | No SVM implementation, trading, L2, or L4 code paths are modified in scoped status checks. Dirty tree includes an unrelated Obsidian smart-env SVM metadata file, so the broad tree is not perfectly clean. |
| L1 remains blocked pending live validation | PASS | No v1 closeout log or feature doc exists; current docs still gate L1 on live warm-worker validation. |

## Queue Candidate Table

Queue path: `artifacts/research/marker_validation_queue_direct`

| # | Candidate | Status | Attempts | PDF URL | Suitability |
|---|---|---:|---:|---|---|
| 1 | `arxiv:2604.24366` | pending | 0 | `https://arxiv.org/pdf/2604.24366.pdf` | Anchor; prior IPC live run parsed this paper with `body_source=marker`, `body_length=56923`, `parse_seconds=39.19`. |
| 2 | `arxiv:2109.07581` | pending | 0 | `https://arxiv.org/pdf/2109.07581.pdf` | Prose-heavy sports betting/COVID paper; direct PDF path avoids Atom API. |
| 3 | `arxiv:1910.08858` | pending | 0 | `https://arxiv.org/pdf/1910.08858.pdf` | Prose-heavy betting-market inefficiency paper; previous blocker was Atom API timeout/429 before Marker parse. |

Counts:

```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

`results.jsonl` is absent.

## Readiness Command

The next live validation may run this prepared queue:

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  warm-process --max-items 3 --json
```

Do not use the old non-direct queue for this validation.

## Caveat

Non-blocking for the fresh direct queue: `MarkerParseQueue.enqueue(..., force=True,
pdf_url=...)` currently resets status and attempts on an existing record but does
not update/add `pdf_url` on that existing record. The prepared fresh queue is not
affected because all three records were newly added with `pdf_url` present. If an
operator tries to retrofit the old queue with `--force --pdf-url`, they should
inspect the queue file afterward or use this fresh direct queue instead.

## Commands Run and Results

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
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
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

Exit code: 0

```text
CLI loaded successfully. Output includes `research-marker-queue`.
```

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 147 items

tests\test_ris_marker_ipc_worker.py .................................... [ 24%]
...                                                                      [ 26%]
tests\test_ris_marker_queue.py ......................................... [ 54%]
...................s...............................................      [100%]

======================= 146 passed, 1 skipped in 2.57s ========================
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

### `python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue_direct counts --json`

Exit code: 0

```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
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
    "status": "pending",
    "attempts": 0,
    "pdf_url": "https://arxiv.org/pdf/2604.24366.pdf"
  },
  {
    "candidate_id": "arxiv:2109.07581",
    "source_url": "https://arxiv.org/abs/2109.07581",
    "arxiv_id": "2109.07581",
    "title": "The Impact of COVID-19 on Sports Betting Markets",
    "status": "pending",
    "attempts": 0,
    "pdf_url": "https://arxiv.org/pdf/2109.07581.pdf"
  },
  {
    "candidate_id": "arxiv:1910.08858",
    "source_url": "https://arxiv.org/abs/1910.08858",
    "arxiv_id": "1910.08858",
    "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
    "status": "pending",
    "attempts": 0,
    "pdf_url": "https://arxiv.org/pdf/1910.08858.pdf"
  }
]
```

### `Get-ChildItem -Force -LiteralPath 'artifacts/research/marker_validation_queue_direct' -Filter 'results.jsonl'`

Exit code: 0

```text
<no output>
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
```

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
```

### Scoped SVM/trading/L2/L4 checks

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

## Blockers or Fixes

No blocker for the next live validation against the fresh direct queue.

Fix later if this path is reused operationally: make `enqueue(..., force=True,
pdf_url=...)` update the existing record's `pdf_url`. That is not required for
the prepared fresh queue.

## Codex Review Summary

Tier: read-only validation review. No mandatory trading/risk execution files were
reviewed. Issues found: no blocker to one live Docker validation against the
fresh direct queue; one non-blocking `--force --pdf-url` caveat noted. Issues
addressed: none, per instruction to change only this review log.
