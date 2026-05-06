# Codex Re-Review - Marker Canonical Academic Parse Queue v0

Date: 2026-05-05
Reviewer: Codex
Scope: Re-review Claude fixes for prior Codex FAIL blockers.
Verdict: PASS

## Decision

Prior Codex FAIL blockers are resolved for offline/code review:

- The code no longer falsely presents Docker/Linux queue processing as warm-worker
  validation. Docker subprocess mode is explicitly documented as cold per paper,
  with warm IPC worker deferred to v1.
- The canonical academic indexing path now rejects non-Marker academic bodies and
  short Marker bodies before chunking/storage.
- Short Marker output is now an auditable failure/retry, not a completed queue item.

Live Docker warm-worker validation may NOT proceed as an acceptance gate. The
current Docker/Linux path still spawns a fresh subprocess per paper and reloads
Marker models per extraction. Only limited diagnostic Docker checks are defensible
at this point, such as enqueue/list/counts and a single cold parse; multi-paper
warm-throughput validation must wait for a persistent warm IPC worker.

## Prior Blocker Status

1. Warm worker was not actually warm: RESOLVED BY SCOPE BLOCK.
   `MarkerParseQueue.process_next()` now documents platform behavior. Windows
   thread mode can pre-load a model dict once per batch. Linux/Docker subprocess
   mode still cold-loads per paper, and the CLI says "cold per paper on
   Linux/Docker" with warm IPC deferred to v1. This blocks live Docker warm-worker
   acceptance validation instead of overclaiming it.

2. Missing Marker-only indexing gate: RESOLVED.
   `IngestPipeline.ingest_external()` now rejects `source_family="academic"` unless
   adapted metadata has `body_source == "marker"` and `body_length >= 5000`.

3. pdfplumber/abstract_fallback/marker_failed could enter canonical embeddings:
   RESOLVED.
   The academic gate rejects `pdf`, `pdfplumber_fallback`, `abstract_fallback`,
   `marker_failed`, `unknown`, and short `marker` bodies before hard stops,
   chunking, and KnowledgeStore writes.

4. Short Marker output marked done: RESOLVED.
   Queue processing now sets `rejected=True`, `exit_code=1`, and a
   `marker_body_too_short` failure reason. It retries as `pending` until
   `MAX_ATTEMPTS`, then becomes `failed`.

5. Queue states/failure_reason explicit: PASS WITH CAVEAT.
   The mutable queue uses simple states (`pending`, `processing`, `done`,
   `failed`), while result attempts include `queue_status`, `failure_reason`,
   `body_source`, `body_length`, `parse_seconds`, `rejected`, and `marker_ready`.
   Retryable failure is represented by `queue_status="pending"` plus attempts and
   failure details in `results.jsonl`, not by a separate queue state name.

6. No L2/SVM/L4/n8n/trading scope creep: PASS.
   Reviewed changes are confined to RIS ingestion/fetching/queue CLI/tests/dev
   logs. No trading, n8n, SVM, or L4 implementation scope was touched.

7. Tests offline and pass: PASS.
   The required targeted tests are offline/deterministic and passed.

## Commands Run

`git status --short`

Output: no output; worktree was clean before this dev log was added.

`git log --oneline -5`

```text
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
38a13c2 docs(ris): short-paper Marker smoke validation - systematic timeout diagnosis
```

`python -m polytool --help`

Result: exit 0. The top-level help loaded and listed `research-marker-queue`.

`git diff`

Output: no output at review start; Claude fixes were already committed in HEAD.

`git show --stat --oneline HEAD`

```text
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
 ...-05-05_marker-canonical-parse-queue-v0-fixes.md | 165 ++++++++++++++
 packages/research/ingestion/extractors.py          |   9 +-
 packages/research/ingestion/fetchers.py            |  55 ++++-
 packages/research/ingestion/marker_queue.py        |  47 +++-
 packages/research/ingestion/pipeline.py            |  28 +++
 tests/test_ris_marker_queue.py                     | 251 ++++++++++++++++++++-
 tools/cli/research_marker_queue.py                 |  12 +-
 7 files changed, 551 insertions(+), 16 deletions(-)
```

`rg --files docs/dev_logs -g "*marker*queue*.md"`

Result: failed because `rg.exe` could not run in this sandbox:

```text
Program 'rg.exe' failed to run: Access is denied
```

Fallback command used:

`Get-ChildItem -Path docs\dev_logs -Filter "*marker*queue*.md" | Select-Object -ExpandProperty FullName`

```text
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-05_codex-review-marker-canonical-parse-queue-v0.md
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-05_marker-canonical-parse-queue-packet.md
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-05_marker-canonical-parse-queue-v0-fixes.md
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-05_marker-canonical-parse-queue-v0.md
```

`python -m pytest tests/test_ris_marker_queue.py tests/test_ris_academic_pdf.py tests/test_ris_scheduler.py`

```text
collected 147 items
146 passed, 1 skipped in 1.69s
```

`python -m polytool research-marker-queue --help`

Result: exit 0. Relevant help text:

```text
Marker Canonical Academic Parse Queue v0. Enqueue arXiv papers, process them
with Marker, and track which papers are RAG-ready (marker_ready=true). On
Windows, Marker models are pre-loaded once per batch (warm). On Linux/Docker,
models reload per paper (subprocess mode; warm IPC worker is v1).

process             Process next N pending items using Marker. Warm batch
                    on Windows (thread mode); cold per paper on
                    Linux/Docker.
```

`git diff --check`

Output: no output; exit 0.

## Review Notes

- `packages/research/ingestion/marker_queue.py` has the canonical
  `is_marker_ready(body_source, body_length)` guard and rejects short Marker
  output during queue processing.
- `packages/research/ingestion/fetchers.py` defaults production academic PDF
  parsing to Marker and returns `marker_failed` instead of pdfplumber fallback
  in explicit/default Marker mode.
- `packages/research/ingestion/pipeline.py` enforces Marker-only academic
  indexing before chunking/storage.
- `tools/cli/research_marker_queue.py` now accurately warns that Docker/Linux
  processing is cold per paper.

## Open Blocker

Implement a real persistent warm Docker worker (likely long-lived subprocess
with IPC) before treating multi-paper live Docker throughput as L1 queue
validation.
