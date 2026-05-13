# Codex Verify - RIS L1 Marker Production Readiness Rollout

**Date:** 2026-05-09
**Reviewer:** Codex
**Objective:** Verify whether RIS L1 Marker Production/Readiness Rollout is accepted as complete and whether L2/PaperQA2 may be activated next.

## Verdict

**FAIL**

L1's functional/operator DoD is substantially satisfied: the Marker queue path is documented, accepted academic papers require `body_source=marker`, pdfplumber is not a production fallback in the canonical path, short/bad parses are rejected or retried, and targeted tests pass.

The rollout is not accepted as complete because the completion protocol is inconsistent in `docs/CURRENT_DEVELOPMENT.md`: the completed L1 rollout remains under **Active Features** as `### Feature 3`, while also being listed under **Recently Completed**. The same file then claims active count is 2. Completion protocol says closed work must be moved to Recently Completed, not duplicated in Active Features.

**L2/PaperQA2 may not be activated next until this documentation-protocol blocker is fixed.**

## Findings

### Blocking

1. `docs/CURRENT_DEVELOPMENT.md` completion protocol is incomplete.
   - Rule line: `docs/CURRENT_DEVELOPMENT.md:18` says completion protocol requires moving the entry to Recently Completed.
   - Active duplicate: `docs/CURRENT_DEVELOPMENT.md:38` still has `### Feature 3: RIS L1 Marker Production Readiness Rollout` under Active Features.
   - Recently Completed row exists: `docs/CURRENT_DEVELOPMENT.md:116`.
   - Architect note says `Active count: 2 (Features 1, 2)` at `docs/CURRENT_DEVELOPMENT.md:172`, contradicting the visible Active Features section.

2. Stale internal source comments/docstrings remain after the status flip.
   - `packages/research/ingestion/marker_queue.py:353` says `L1 production is NOT unblocked. Live validation required before production deployment of this path.`
   - `packages/research/ingestion/marker_ipc_worker.py:8`, `:17`, `:158`, and `:270` still present active-looking `<=10s/paper` warm-worker target language.
   - This is not a runtime behavior failure, but it contradicts the current rollout truth and should be cleaned before re-review.

## Verification Matrix

| Check | Status | Evidence |
|---|---|---|
| Feature 3 activated as RIS L1 rollout | PASS with caveat | `CURRENT_DEVELOPMENT.md` records Feature 3 as RIS L1 rollout, but it remains in Active after completion. |
| L1 DoD concrete/operator-focused | PASS | Feature doc and runbook define enqueue -> warm-process -> inspect, output paths, queue states, recovery. |
| Completion protocol complete | FAIL | Feature doc and INDEX exist, but `CURRENT_DEVELOPMENT.md` copied rather than moved Feature 3. |
| Operator path documented simply | PASS | `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` gives direct commands and expected output. |
| Accepted L1 papers require `body_source=marker` | PASS | `marker_queue.is_marker_ready()` and `IngestPipeline.ingest_external()` enforce Marker body and length gates. |
| pdfplumber not production fallback | PASS | Production/default parser is Marker; pdfplumber is debug/auto legacy and rejected by academic gate. |
| Queue/error states block bad parses | PASS | `MAX_ATTEMPTS=3`, `MIN_MARKER_BODY_LENGTH=5000`, non-marker and short Marker output are rejected/retried. |
| Tests/smokes support L1 status | PASS | Targeted suite: 158 passed, 1 skipped. Extra academic PDF suite: 39 passed. |
| Warm-worker timing honesty in docs | PASS for current operator docs | Current docs preserve 45.55s/69.73s/48.31s and reject <=10s as unrealistic. Source comments still need cleanup. |
| L2/PaperQA2 and L4 not prematurely implemented | PASS | Work packets remain stubs; package/tool search found no implementation surface beyond benchmark recommendation labels. |
| No trading/PMXT/Track 1 files touched | PASS | Rollout commit touched RIS docs plus `tools/cli/research_marker_queue.py` only. |

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
- `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - PaperQA2 RAG Control Flow.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Multi-source Academic Harvesters.md`
- `packages/research/ingestion/marker_queue.py`
- `packages/research/ingestion/marker_ipc_worker.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/pipeline.py`
- `packages/research/ingestion/adapters.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `tests/test_ris_academic_pdf.py`

## Commands Run and Results

### `git status --short`

Initial output:

```text
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
```

These appeared before this verification and were not touched.

### `git log --oneline -5`

```text
d2c0c27 feat(ris): L1 Marker Production Readiness Rollout - Feature 3 closed
932b839 pipeline improvements
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
```

### `python -m polytool --help`

Result: exit 0. CLI loaded successfully and listed `research-marker-queue` under RIS commands.

### `git diff --stat`

Initial output:

```text
 .../.smart-env/event_logs/event_logs.ajson         | 32 +++++++++++++++++++++-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    | 25 +++++++++++++++++
 2 files changed, 56 insertions(+), 1 deletion(-)
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --name-status`

```text
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --name-status -- packages tools tests docs`

```text
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git show --stat --oneline --summary HEAD`

```text
d2c0c27 feat(ris): L1 Marker Production Readiness Rollout - Feature 3 closed
 docs/CURRENT_DEVELOPMENT.md                        |  28 ++-
 docs/CURRENT_STATE.md                              |  54 ++++-
 docs/INDEX.md                                      |   5 +-
 ...9_ris-l1-marker-production-readiness-rollout.md | 140 ++++++++++++
 ...E-ris-l1-marker-production-readiness-rollout.md | 156 ++++++++++++++
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  10 +-
 docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md          | 237 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 |   8 +-
 8 files changed, 618 insertions(+), 20 deletions(-)
 create mode 100644 docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md
 create mode 100644 docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md
 create mode 100644 docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
```

### `git diff HEAD~1 HEAD --name-status -- packages tools tests docs`

```text
M	docs/CURRENT_DEVELOPMENT.md
M	docs/CURRENT_STATE.md
M	docs/INDEX.md
A	docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md
A	docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
A	docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
M	tools/cli/research_marker_queue.py
```

### User-requested grep

Command:

```powershell
rg -n "body_source=marker|pdfplumber|rag_ready|marker_failed|Marker Production|PaperQA2|Multi-source" docs packages tools tests
```

Result: exit 0, 1053 matching lines. Reviewed hits across docs, packages, tools, and tests. Relevant evidence:

```text
docs\runbooks\RIS_MARKER_QUEUE_RUNBOOK.md:149:marker_ready = body_source == "marker" AND body_length >= 5000 chars
docs\runbooks\RIS_MARKER_QUEUE_RUNBOOK.md:153:Papers with `body_source=marker_failed`, `pdfplumber`, `abstract_fallback`, or
packages\research\ingestion\marker_queue.py:16:  marker_ready = body_source == "marker" AND body_length >= MIN_MARKER_BODY_LENGTH
packages\research\ingestion\marker_queue.py:17:  pdfplumber, pdfplumber_fallback, abstract_fallback, marker_failed: NOT marker_ready.
packages\research\ingestion\pipeline.py:290:                        f"academic_marker_gate: body_source={_body_source!r} with "
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - PaperQA2 RAG Control Flow.md:16:# Work Packet (stub) - PaperQA2 RAG Control Flow
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Multi-source Academic Harvesters.md:16:# Work Packet (stub) - Multi-source Academic Harvesters
```

### Completion-protocol grep

Command:

```powershell
rg -n "### Feature 3: RIS L1 Marker Production Readiness Rollout|Recently Completed|RIS L1 Marker Production Readiness Rollout" docs/CURRENT_DEVELOPMENT.md
```

Output:

```text
18:   - Move entry to Recently Completed
38:### Feature 3: RIS L1 Marker Production Readiness Rollout
112:## Recently Completed (rolling 30 days)
116:| RIS L1 Marker Production Readiness Rollout                   | 2026-05-09 | RIS      | `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md` - repeatable operator path (enqueue->warm-process->inspect); runbook at `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`; stale "L1 gated" CLI text removed; 158 tests pass; L1 DoD all criteria met. L2/L4 now unblocked. Dev log: `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md`. |
172:- **RIS L1 Marker Production Readiness Rollout is COMPLETE (2026-05-09).** L1 DoD fully met: repeatable operator path (enqueue->warm-process->inspect), Marker-only gate enforced, no pdfplumber fallback, queue state machine and recovery documented, bad/short parse rejection, output inspection commands. Feature doc: `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`. Runbook: `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`. Stale "L1 gated" CLI text removed. 158 tests pass. **L2 PaperQA2 RAG Control Flow and L4 Multi-source Harvesters are now unblocked.** Active count: 2 (Features 1, 2). Dev log: `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md`.
```

### Stale status/timing grep

Command:

```powershell
rg -n "L1 production remains gated|L1 production is NOT unblocked|live validation required|production remains gated|production gated|<=10s" docs packages tools tests
```

Relevant current-source output:

```text
packages\research\ingestion\marker_queue.py:353:        NOTE: L1 production is NOT unblocked. Live validation required before
packages\research\ingestion\marker_ipc_worker.py:8:(~80-270s on RTX 2070 Super), failing the <=10s/paper gate for papers 2+.
packages\research\ingestion\marker_ipc_worker.py:17:        result = worker.parse(pdf_path)         # warm parse, <=10s for papers 2+
packages\research\ingestion\marker_ipc_worker.py:158:            result = worker.parse(path)   # papers 2+: warm, <=10s on RTX 2070 Super
packages\research\ingestion\marker_ipc_worker.py:270:        Subsequent parse() calls return from warm VRAM (target: <=10s/paper).
```

Current operator docs also contain historical `<=10s` references, but those are mostly marked rejected/superseded and preserve the measured warm-worker timings.

### Marker readiness grep

Command:

```powershell
rg -n 'body_source == "marker"|body_source=marker|marker_ready =|MIN_MARKER_BODY_LENGTH|_ACADEMIC_MIN_MARKER_BODY_LENGTH|academic_marker_gate' packages tools tests docs/features docs/runbooks
```

Relevant output:

```text
packages\research\ingestion\pipeline.py:23:# Must stay in sync with marker_queue.MIN_MARKER_BODY_LENGTH (= 5000).
packages\research\ingestion\pipeline.py:24:_ACADEMIC_MIN_MARKER_BODY_LENGTH = 5000
packages\research\ingestion\pipeline.py:279:            _marker_ready = (
packages\research\ingestion\pipeline.py:281:                and _body_length >= _ACADEMIC_MIN_MARKER_BODY_LENGTH
packages\research\ingestion\pipeline.py:290:                        f"academic_marker_gate: body_source={_body_source!r} with "
packages\research\ingestion\marker_queue.py:16:  marker_ready = body_source == "marker" AND body_length >= MIN_MARKER_BODY_LENGTH
packages\research\ingestion\marker_queue.py:33:MIN_MARKER_BODY_LENGTH = 5000  # chars; below this even a "marker" parse is not rag-ready
packages\research\ingestion\marker_queue.py:58:    return body_source == "marker" and body_length >= MIN_MARKER_BODY_LENGTH
tests\test_ris_marker_queue.py:805:        assert "academic_marker_gate" in result.reject_reason
```

### L2/L4 implementation grep

Command:

```powershell
rg -n "PaperQA2|paperqa|Multi-source|SemanticScholarFetcher|SSRNFetcher|NBERFetcher|OpenReviewFetcher|CrossrefUnpaywallFetcher|research-query" packages tools tests docs/features docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md
```

Relevant output:

```text
docs/CURRENT_STATE.md:1782:- L2 PaperQA2 activation - **NOW UNBLOCKED** (L1 production readiness rollout COMPLETE 2026-05-09). See `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`.
docs/CURRENT_STATE.md:1846:- L2 PaperQA2 RAG Control Flow - stub; NOW UNBLOCKED by L1 completion.
docs/CURRENT_STATE.md:1847:- L4 Multi-source Academic Harvesters - stub; NOW UNBLOCKED (gated on L1 + L3; both complete).
packages\research\eval_benchmark\recommender.py:18:    "C": "PaperQA2-style retrieval (Layer 2)",
docs/features\FEATURE-ris-l1-marker-production-readiness-rollout.md:52:| L2: PaperQA2 RAG Control Flow | Stub | Gated on L1 completion (NOW UNBLOCKED) |
docs/features\FEATURE-ris-l1-marker-production-readiness-rollout.md:54:| L4: Multi-source Academic Harvesters | Stub | Gated on L1 + L3 |
```

No PaperQA2 or L4 harvester implementation files were found.

### `python -m polytool research-marker-queue --help`

Output included:

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
    warm-process        Process next N pending items using MarkerIPCWorker
                        (warm IPC, Linux/Docker). On Windows, falls back to
                        warm thread worker. L1 production path - IPC warm-
                        worker validated 2026-05-08 (Feature 3 closed).
```

### `python -m polytool research-marker-queue warm-process --help`

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

### Targeted tests named in Claude dev log

Command:

```powershell
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py -x -q --tb=short
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 159 items

tests\test_ris_marker_queue.py ......................................... [ 25%]
...................s.................................................... [ 71%]
..                                                                       [ 72%]
tests\test_ris_marker_ipc_worker.py .................................... [ 94%]
........                                                                 [100%]

======================= 158 passed, 1 skipped in 3.18s ========================
```

### Extra offline academic PDF unit suite

Command:

```powershell
python -m pytest tests/test_ris_academic_pdf.py -q --tb=short
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 39 items

tests\test_ris_academic_pdf.py .......................................   [100%]

============================= 39 passed in 0.95s ==============================
```

## Decisions

- No Docker-heavy validation was run.
- No queues or artifacts were mutated intentionally.
- No code or docs were edited except this review dev log.
- Overall FAIL is based on completion-protocol inconsistency, not on Marker queue runtime behavior.

## Required Fixes Before Re-Review

1. Remove the completed RIS L1 rollout block from the Active Features section of `docs/CURRENT_DEVELOPMENT.md`, leaving it only in Recently Completed and notes/history.
2. Clean stale internal comments/docstrings in `packages/research/ingestion/marker_queue.py` and `packages/research/ingestion/marker_ipc_worker.py` that still say L1 is blocked or imply `<=10s/paper` warm parsing is the current target.
3. Re-run this verification or at minimum re-run:
   - `rg -n "### Feature 3: RIS L1 Marker Production Readiness Rollout|Recently Completed|RIS L1 Marker Production Readiness Rollout" docs/CURRENT_DEVELOPMENT.md`
   - `rg -n "L1 production remains gated|L1 production is NOT unblocked|live validation required|production remains gated|production gated|<=10s" docs packages tools tests`
   - `python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py -x -q --tb=short`
