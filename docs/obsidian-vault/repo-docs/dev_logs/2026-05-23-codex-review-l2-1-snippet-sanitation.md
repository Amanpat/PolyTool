---
title: Codex Review L2 1 Snippet Sanitation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_codex-review-l2-1-snippet-sanitation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - L2.1 Deliverable C Snippet Sanitation

**Date:** 2026-05-23
**Reviewer:** Codex
**Verdict:** PASS WITH CONCERNS

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-snippet-sanitation.md`
- `packages/research/synthesis/academic_query.py`
- `tests/test_research_query.py`
- Adjacent/out-of-scope diffs inspected for scope leakage:
  - `packages/research/ingestion/marker_queue.py`
  - `tools/cli/research_marker_queue.py`
  - `tests/test_ris_marker_queue.py`
  - `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - `docs/CURRENT_STATE.md`

## Review Findings

Deliverable C implementation is render-time only. `_sanitize_snippet()` is called while
building `AcademicCitation.best_snippet`; raw KnowledgeStore `claim_text` is not written
back or mutated.

The sanitizer covers the required artifact classes:

- Known Marker tags including `<sup>`, `<sub>`, `<br>`, and `<a ...>`.
- Marker page anchors like `(#page-18-0)`.
- Markdown heading markers like `####`.
- Excess whitespace runs.

Retrieval behavior was not changed in `academic_query.py`. The query flow still uses
`query_knowledge_store_for_rrf()` against `source_family="academic"` and retains the
existing Marker-ready metadata guard. No ChromaDB linkage, semantic fallback, embedding
path, parser-setting change, or benchmark-baseline change was introduced by the snippet
sanitation diff.

## Coverage Gaps Found / Fixed

Fixed one test-only coverage weakness in `tests/test_research_query.py`:

- Removed a duplicated `_sanitize()` helper definition in `TestSanitizeSnippet`.
- Strengthened `test_stored_claim_text_not_modified` to inspect the same in-memory
  KnowledgeStore instance that was queried, instead of creating a fresh store.

Remaining non-blocking concern:

- `<br>` tags are stripped rather than replaced with a separator. This removes the
  artifact, but a snippet like `line one<br>line two` becomes `line oneline two`. Existing
  acceptance checks only require artifact removal; if operator readability is tightened,
  replace line-break tags with a space or newline in a future tiny follow-up.

## Commands Run

```powershell
git status --short
```

Result: dirty worktree with many pre-existing changes, including unrelated Obsidian/vault
files and WP-2 Marker queue changes. Review avoided unrelated files except for scope
inspection.

```powershell
git log --oneline -5
```

Result:

```text
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
```

```powershell
python -m polytool --help
```

Result: exit 0; CLI loads and lists `research-query` and `research-marker-queue`.

```powershell
python -m pytest tests/test_research_query.py -q --tb=short
```

Result:

```text
83 passed in 0.97s
```

```powershell
python -m pytest tests/test_ris_marker_queue.py -q --tb=short
```

Result:

```text
177 passed, 1 skipped in 3.38s
```

```powershell
python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short
```

Result:

```text
260 passed, 1 skipped in 3.44s
```

```powershell
rg "academic_papers|semantic_fallback|_query_chroma|chromadb|ChromaDB|sentence_transformer|embedding" packages/research/synthesis/academic_query.py packages/research/ingestion/marker_queue.py tools/cli/research_marker_queue.py tests/test_research_query.py
```

Result: only the existing `academic_query.py` docstring note says this version does not
query ChromaDB.

## Verdict

PASS WITH CONCERNS.

Deliverable C is correctly scoped in the implementation file and is covered by focused
unit and integration tests. Operator-facing snippets are sanitized, stored KnowledgeStore
content remains unchanged, and focused tests show no accidental retrieval behavior change.

The concern is worktree hygiene: the current diff contains substantial WP-2 Marker queue
and runbook changes unrelated to snippet sanitation. Those should be reviewed/committed
separately from the L2.1 Deliverable C patch.

## Recommended Next Action

Land Deliverable C separately from the WP-2 Marker queue changes, or explicitly split the
worktree before merge. If operator snippet readability is tightened beyond artifact
removal, add a small follow-up to replace `<br>` tags with a space or newline instead of
deleting them.
