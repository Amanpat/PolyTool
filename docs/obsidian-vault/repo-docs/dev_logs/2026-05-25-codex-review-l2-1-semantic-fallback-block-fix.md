---
title: Codex Review L2 1 Semantic Fallback Block Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-block-fix.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - L2.1 Semantic Fallback Block Fix

**Date:** 2026-05-25
**Reviewer:** Codex
**Verdict:** BLOCK

## Objective

Review the L2.1 Deliverable B block fix. Done means the semantic fallback is
actually present in the live academic query path, `academic_papers` linkage is
usable, acceptance tests pass without xfail, and L2.1 can be declared complete
or remains blocked with exact reasons.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-semantic-fallback-block-fix.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-semantic-fallback.md`
- `packages/research/synthesis/academic_query.py`
- `tools/cli/research_query.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_research_query.py`
- `tests/test_ris_marker_queue.py`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

## Git Diff / Scope

The dirty diff includes Deliverable A Chroma linkage work and Deliverable B query
work, not just a repeat of Deliverable A:

- `packages/research/synthesis/academic_query.py` now has `_open_chroma_collection()`,
  `_query_chroma_semantic()`, `_chroma_collection` injection, `ks_doc_id` resolution,
  and `AcademicQueryResult.retrieval_mode`.
- `tools/cli/research_query.py` emits `retrieval_mode`.
- `tests/test_research_query.py` has un-xfailed semantic acceptance cases using a
  fake Chroma collection.

Scope note: the worktree also contains large unrelated Obsidian/vault changes and
Marker queue/runbook changes. I did not modify implementation code or vault files.

## Retrieval Mode Evidence

Code inspection confirms:

- `academic_query.py` line 425 opens the real Chroma collection unless a test
  collection is injected.
- `_query_chroma_semantic()` reads `ks_doc_id` from Chroma metadata and deduplicates
  by it.
- `query_academic_corpus()` resolves each semantic hit through
  `ks.get_source_document(ks_doc_id)` before building citations.
- `AcademicQueryResult.retrieval_mode` exists and is surfaced by `research-query`.

Blocking concern: `_open_chroma_collection()` constructs
`SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5")` before
calling `get_collection("academic_papers")`. In this local environment, where the
collection is absent and the model is not locally cached, ordinary queries and unit
tests try Hugging Face repeatedly and time out instead of quickly falling back to
lexical retrieval.

## Commands Run

`git status --short`

Result: dirty worktree with target files plus large unrelated Obsidian/vault
changes. No files were reverted.

`git log --oneline -5`

```text
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
```

`python -m polytool --help`

Result: exit 0; CLI loaded and listed `research-query` and `research-marker-queue`.

`python -m pytest tests/test_research_query.py -q --tb=short`

Result: timed out after 120s. Output reached:

```text
collected 90 items
tests\test_research_query.py
```

`python -m pytest tests/test_research_query.py::TestQueryAcademicCorpus::test_empty_ks_returns_fallback -q --tb=short`

Result: timed out after 120s on a single empty-KS test. This isolates the
slow/failing behavior to the query path's Chroma opener, not to the semantic fake
tests themselves.

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

First 120s run timed out partway through. Re-run with 300s timeout completed:

```text
204 passed, 1 skipped in 250.78s (0:04:10)
```

`python -m polytool research-marker-queue check-chroma-links --json`

```text
{"error": "Collection [academic_papers] does not exist", "collection": "academic_papers", "hint": "Run 'index-done --reindex-chroma' to populate the collection first.", "exit_code": 1}
```

`python -m polytool research-query --question "LLM" --json`

Result: exit 1, `--json` is not a supported flag for `research-query`.

`python -m polytool research-query --question "LLM"`

Result: timed out after 120s. Output showed repeated Hugging Face connection
attempts for `BAAI/bge-large-en-v1.5` before timeout.

`python -m polytool research-query --question "weather forecast"`

Result: timed out after 120s with the same Hugging Face model lookup retries.

Forced-offline diagnostic runs:

```powershell
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; python -m polytool research-query --question "LLM"
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; python -m polytool research-query --question "language model financial prediction"
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; python -m polytool research-query --question "what does this paper say about hallucination"
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; python -m polytool research-query --question "weather forecast"
```

Results:

- `LLM`: `had_fallback=false`, `retrieval_mode=lexical`, 4 citations; first
  citation is the unrelated Bellman paper, target LLM paper is rank 2 with
  `claim_count=11`.
- `language model financial prediction`: `had_fallback=true`,
  `retrieval_mode=lexical`, 0 citations.
- `what does this paper say about hallucination`: `had_fallback=true`,
  `retrieval_mode=lexical`, 0 citations.
- `weather forecast`: `had_fallback=true`, `retrieval_mode=lexical`, 0 citations.

Targeted tests with forced-offline flags:

```text
python -m pytest tests/test_research_query.py::TestSemanticRetrievalAcceptanceGaps -q --tb=short -rA
5 passed in 10.70s

python -m pytest tests/test_research_query.py::TestSanitizeSnippet tests/test_research_query.py::TestSanitizeSnippetIntegration -q --tb=short -rA
31 passed in 10.75s
```

No `pytest.mark.xfail` remains in `tests/test_research_query.py`, though the
class docstring still says the tests are intentionally xfailed.

## Acceptance Case Results

| Case | Result | Verdict |
|---|---|---|
| AT-1 `LLM` | Default live query timed out. Forced-offline lexical diagnostic still returns Bellman first and LLM paper second. Fake-Chroma unit test passes. | FAIL live / PASS injected |
| AT-2 `language model financial prediction` | Default live query path blocked by model lookup behavior. Forced-offline lexical diagnostic returns 0 citations. Fake-Chroma unit test passes. | FAIL live / PASS injected |
| AT-3 `what does this paper say about hallucination` | Default live query path blocked by model lookup behavior. Forced-offline lexical diagnostic returns 0 citations. Fake-Chroma unit test passes. | FAIL live / PASS injected |
| AT-4 `weather forecast` | Default live query timed out. Forced-offline diagnostic rejects cleanly with 0 citations. | FAIL default / PASS diagnostic |
| AT-5 snippet sanitation | Unit/integration tests pass. Forced-offline `LLM` output no longer includes `####` or `(#pag` in the observed snippets. | PASS |

## Findings

### Blocking: default query path can hang before lexical fallback

`query_academic_corpus()` calls `_open_chroma_collection()` for every query, and
that helper initializes the BGE sentence-transformer embedding function before
it knows whether `academic_papers` exists. With no local model cache and no
network access, even a single empty-KS unit test timed out after 120 seconds.
This violates the requirement that semantic retrieval be an optional fallback
when Chroma is absent/unavailable.

### Blocking: `academic_papers` linkage is not usable locally

`check-chroma-links --json` reports the `academic_papers` collection does not
exist. Chroma linkage is therefore not usable in the current local state, and
live semantic hits cannot be proven through real `ks_doc_id` metadata.

### Blocking: requested acceptance test plan does not pass

`tests/test_research_query.py` timed out under the normal environment, and the
default live `research-query` smokes timed out before answering. The un-xfailed
semantic acceptance tests pass only through the injected fake Chroma collection,
not through the live local `academic_papers` collection.

### Non-blocking: Deliverable B exists in code

This is not Deliverable A repeated. The query implementation has a real Chroma
query hook, `ks_doc_id` resolution, Marker-ready filtering, semantic mode
metadata, and CLI JSON propagation. The issue is operational readiness and the
absent collection/model fallback behavior.

## Scope Violations

No new scope violation was introduced by this review. I did not run GPU parsing,
the 29-paper validation, or a 3-paper sample. I did not touch Marker parser logic,
SVM enforce, benchmark baselines, or implementation code.

## Verdict

BLOCK.

L2.1 is not complete. A 3-paper category sample is not safe next because the
single-paper acceptance path still cannot run cleanly in the default environment,
and the `academic_papers` collection is absent.

## Required Next Fix

Fix `_open_chroma_collection()` so Chroma collection existence is checked before
the sentence-transformer embedding function is initialized, or otherwise ensure
missing Chroma/model assets fail fast without Hugging Face retries. Then populate
and verify `academic_papers`, rerun `check-chroma-links --json`, rerun the full
requested pytest commands, and rerun the four live acceptance smokes without
forced offline environment overrides.
