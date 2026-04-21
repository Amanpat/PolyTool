# RIS Phase 2 Ingest/Review Integration

Date: 2026-04-08

Scope note: this log covers the RIS ingest/evaluation/review-queue integration work for this objective only. The repository already had unrelated modified files in the worktree before and during this task; those changes were not reverted or expanded here.

## Files changed and why

- `packages/research/ingestion/pipeline.py`
  - Made evaluator outcomes drive the final ingest disposition.
  - `ACCEPT` now continues into normal knowledge-store ingest.
  - `REVIEW` and fail-closed/blocked outcomes now enqueue into `pending_review` instead of disappearing.
  - `REJECT` now exits cleanly without ingest and without implicit review-queue insertion.
  - Added durable result fields: `disposition`, `disposition_reason`, `pending_review_id`.

- `packages/research/ingestion/review_integration.py`
  - New helper module for disposition classification and stable pending-review snapshot construction.
  - Centralizes mapping from evaluator gate output to operator-visible outcomes:
    - `accepted`
    - `queued_for_review`
    - `rejected`
    - `blocked`

- `packages/research/ingestion/adapters.py`
  - Ensured adapter output carries durable source references into the pipeline.
  - Added `source_id` and `source_metadata_ref` metadata so queued review entries can point back to the raw source/cache artifact.

- `packages/research/ingestion/acquisition_review.py`
  - Expanded acquisition review records with disposition-facing fields:
    - `disposition`
    - `disposition_reason`
    - `gate`
    - `pending_review_id`

- `tools/cli/research_ingest.py`
  - Surfaced true post-evaluation disposition in human output and JSON output.
  - Added `--artifacts-dir` for durable evaluator artifacts.
  - Updated run-log metadata/counts so `accepted`, `queued_for_review`, `rejected`, and `blocked` are operator-visible.
  - Clamped run-log duration to a tiny positive value to avoid timer-resolution flakes.

- `tools/cli/research_acquire.py`
  - Surfaced true disposition/gate/pending-review state in human output, JSON output, acquisition review records, and run-log metadata.
  - Added `--artifacts-dir` for evaluator artifact persistence.
  - Updated search-mode output to summarize accepted/queued/blocked/rejected counts.
  - Clamped run-log duration to a tiny positive value to avoid timer-resolution flakes.

- `tests/test_ris_ingestion_integration.py`
  - Added focused coverage for:
    - `ACCEPT`
    - `REVIEW -> pending_review`
    - `REJECT`
    - fail-closed/malformed-provider-output -> `blocked`
    - idempotent queue insertion
  - Added CLI JSON assertions for accepted vs queued-for-review output.

- `tests/test_ris_research_acquire_cli.py`
  - Added focused acquire-path coverage for:
    - review queue insertion
    - accepted ingest
    - operator-visible JSON fields
    - acquisition review record propagation

## Commands run + output

### Focused pytest suite

Command:

```powershell
pytest -q tests/test_ris_ingestion_integration.py tests/test_ris_research_acquire_cli.py tests/test_ris_review_queue.py tests/test_ris_monitoring.py
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 97 items

tests\test_ris_ingestion_integration.py ..................               [ 18%]
tests\test_ris_research_acquire_cli.py ................                  [ 35%]
tests\test_ris_review_queue.py ......                                    [ 41%]
tests\test_ris_monitoring.py ........................................... [ 85%]
..............                                                           [100%]

============================= 97 passed in 5.28s ==============================
```

### CLI smoke: accepted path

Command:

```powershell
python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_research.md --json --priority-tier priority_1 --artifacts-dir artifacts/research/eval_smoke_accept
```

Output:

```json
{
  "doc_id": "c54880ed78a0234714242a07388e1ddef6f0eb5727deff2505f5f9d54d8d0fd9",
  "chunk_count": 1,
  "rejected": false,
  "reject_reason": null,
  "gate": "ACCEPT",
  "disposition": "accepted",
  "disposition_reason": null,
  "pending_review_id": null,
  "scores": {
    "total": 12,
    "relevance": 3,
    "novelty": 3,
    "actionability": 3,
    "credibility": 3,
    "composite_score": 3.0,
    "simple_sum_score": 12,
    "priority_tier": "priority_1",
    "reject_reason": null
  }
}
```

### CLI smoke: queued-for-review path

Command:

```powershell
python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_research.md --json --artifacts-dir artifacts/research/eval_smoke_review
```

Output:

```json
{
  "doc_id": "",
  "chunk_count": 0,
  "rejected": true,
  "reject_reason": null,
  "gate": "REVIEW",
  "disposition": "queued_for_review",
  "disposition_reason": "Manual placeholder - human review required.",
  "pending_review_id": "661963471108df884429ba3ed90b517922dae3c97f30b89a0a7e798b2861fba3",
  "scores": {
    "total": 12,
    "relevance": 3,
    "novelty": 3,
    "actionability": 3,
    "credibility": 3,
    "composite_score": 3.0,
    "simple_sum_score": 12,
    "priority_tier": "priority_3",
    "reject_reason": null
  }
}
```

### Full pytest suite

Command:

```powershell
pytest -q
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.12.0
collected 3782 items / 3 deselected / 3779 selected

... full suite output omitted here for brevity ...

========= 3779 passed, 3 deselected, 25 warnings in 120.79s (0:02:00) =========
```

## Test results

- Focused ingest/eval/review/monitoring suite passed: `97 passed`.
- Full repository pytest suite passed: `3779 passed, 3 deselected`.
- Manual accepted CLI smoke produced:
  - `gate=ACCEPT`
  - `disposition=accepted`
  - `pending_review_id=null`
- Manual review CLI smoke produced:
  - `gate=REVIEW`
  - `disposition=queued_for_review`
  - non-null `pending_review_id`

## Final disposition mapping

| Evaluator / pipeline outcome | Final disposition | Durable record |
| --- | --- | --- |
| `ACCEPT` | `accepted` | Normal knowledge-store ingest, evaluator artifact (when enabled), operator-visible CLI/JSON/run-log metadata |
| `REVIEW` | `queued_for_review` | `pending_review` row with gate snapshot, source metadata reference, provider/model/scores, operator-visible CLI/JSON/acquisition-review/run-log metadata |
| `REJECT` | `rejected` | Clean non-ingest result with reject reason, evaluator artifact/log trail when enabled, operator-visible CLI/JSON/acquisition-review/run-log metadata |
| fail-closed / malformed provider output / scorer failure | `blocked` | `pending_review` row with gate snapshot and fail-closed reason, operator-visible CLI/JSON/acquisition-review/run-log metadata |

## Follow-up needed for monitoring / metrics

- Add a dedicated downstream metric split for `queued_for_review` vs `blocked` vs `rejected` so health/reporting can distinguish:
  - quality rejection
  - human-review backlog
  - evaluator/provider failure
- Consider exposing `pending_review` queue depth and age in the existing monitoring surface so blocked/fail-closed accumulation is visible without manual DB inspection.
