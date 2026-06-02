# Codex Review - L2.1 Semantic Fallback Fast-Fail

**Date:** 2026-05-25
**Reviewer:** Codex
**Verdict:** BLOCK

## Objective

Review the L2.1 Deliverable B fast-fail Chroma fix. Done means default
`research-query` does not hang when Chroma/model assets are absent, semantic
retrieval works when Chroma is usable, and acceptance cases are classified
honestly.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-25_l2-1-semantic-fallback-fast-fail.md`
- `docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-block-fix.md`
- `packages/research/synthesis/academic_query.py`
- `tools/cli/research_query.py`
- `packages/polymarket/rag/embedder.py`
- `tests/test_research_query.py`
- `tests/test_ris_marker_queue.py`

## Git Diff / Scope

`git status --short` showed a very large unrelated dirty tree under
`docs/obsidian-vault/`, plus root context-file changes. I did not revert or
modify those files.

The relevant diff is scoped to the L2.1 academic query/test path:

- `packages/research/synthesis/academic_query.py` adds Chroma opening,
  semantic query, `ks_doc_id` resolution, `retrieval_mode`, and
  `semantic_unavailable_reason`.
- `tests/test_research_query.py` adds fake-Chroma semantic acceptance tests and
  Chroma opener fast-fail tests.

This is not a broad unrelated retrieval refactor, but the live query path is now
semantic-first when `academic_papers` exists, even though the spec described a
lexical-primary semantic fallback. That matters for the weather-control case.

## Code Review Evidence

Positive:

- `_open_chroma_collection()` now calls `client.list_collections()` before
  `client.get_collection("academic_papers")`.
- It opens the collection without attaching a Chroma embedding function, avoiding
  the previous persisted-EF conflict.
- Missing `academic_papers` returns `(None, reason)` and does not call
  `get_collection()`.
- Semantic hits are joined through `ks_doc_id` via `ks.get_source_document()`
  before citations are emitted.

Blocking:

- `packages/research/synthesis/academic_query.py:361-363` still instantiates
  `SentenceTransformerEmbedder()` inside `_query_chroma_semantic()` whenever a
  Chroma collection is present. If the BGE model is not locally cached, this
  triggers Hugging Face retries and can hang before lexical fallback.
- The fake-Chroma acceptance tests inject `_chroma_collection`, but
  `_query_chroma_semantic()` still initializes the real embedder before trying
  `query_texts`, so the tests are not offline-safe when the model is absent.
- The semantic path has no relevance threshold. With a populated one-paper
  collection, unrelated queries can become `had_fallback=false` nearest-neighbor
  hits instead of honest rejections.

## Commands Run

`git status --short`

Result: dirty worktree with target files plus large unrelated
`docs/obsidian-vault/` changes. No files were reverted.

`git log --oneline -5`

```text
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A -- closeout log
3348e79 feat(ris): L2.1 Deliverable C -- display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout -- PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
```

`python -m polytool --help`

Result: exit 0; CLI loaded and listed `research-query` and
`research-marker-queue`.

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

```text
204 passed, 1 skipped in 6.93s
```

`python -m polytool research-marker-queue check-chroma-links --json`

```json
{
  "collection": "academic_papers",
  "chroma_path": "kb\\rag\\index",
  "total_chunks": 25,
  "unique_papers": 1,
  "valid_ks_doc_id": 25,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0,
  "not_in_ks_doc_ids": []
}
```

`python -m pytest tests/test_research_query.py -q --tb=short`

Result: timed out after 180s, then timed out again after 360s. Output reached:

```text
collected 94 items
tests\test_research_query.py ........................................... [ 45%]
...........................................
```

Verbose isolation:

`python -m pytest tests/test_research_query.py -vv --tb=short`

Result: timed out after 180s at:

```text
tests/test_research_query.py::TestSemanticRetrievalAcceptanceGaps::test_abbreviation_query_llm_finds_large_language_model_paper_not_bellman
```

Targeted fake-Chroma test:

`python -m pytest tests/test_research_query.py::TestSemanticRetrievalAcceptanceGaps::test_abbreviation_query_llm_finds_large_language_model_paper_not_bellman -vv --tb=short`

Result: timed out after 120s after collecting the single test. This shows the
fake collection does not prevent the real embedder/model path from running.

Chroma opener targeted tests:

`python -m pytest tests/test_research_query.py::TestOpenChromaCollectionFastFail -q --tb=short`

```text
4 passed in 0.73s
```

Snippet sanitation targeted tests:

`python -m pytest tests/test_research_query.py::TestSanitizeSnippet tests/test_research_query.py::TestSanitizeSnippetIntegration -q --tb=short`

```text
31 passed in 3.61s
```

## Timeout Verification

All four default `research-query` acceptance commands timed out after 120s:

- `python -m polytool research-query --question "LLM"`
- `python -m polytool research-query --question "language model financial prediction"`
- `python -m polytool research-query --question "what does this paper say about hallucination"`
- `python -m polytool research-query --question "weather forecast"`

Each produced repeated Hugging Face retry output for
`BAAI/bge-large-en-v1.5`, including:

```text
Retrying in 1s [Retry 1/5].
Retrying in 2s [Retry 2/5].
Retrying in 4s [Retry 3/5].
Retrying in 8s [Retry 4/5].
Retrying in 8s [Retry 5/5].
```

The underlying socket error was:

```text
Failed to establish a new connection: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions
```

The missing-collection opener problem is fixed, but the missing-model problem is
not fixed when `academic_papers` exists.

## Acceptance Case Results

| Case | Result | Classification |
|---|---|---|
| `LLM` | Default live query timed out after 120s on BGE Hugging Face retries. Fake-Chroma unit test also timed out after 120s. | FAIL |
| `language model financial prediction` | Default live query timed out after 120s on BGE Hugging Face retries. | FAIL |
| `what does this paper say about hallucination` | Default live query timed out after 120s on BGE Hugging Face retries. | FAIL |
| `weather forecast` | Default live query timed out after 120s on BGE Hugging Face retries. Also not honestly safe in code because semantic nearest-neighbor has no rejection threshold. | FAIL / BLOCKED |

## Chroma / Linkage Result

The `academic_papers` collection exists locally and linkage is structurally
valid:

- `total_chunks=25`
- `unique_papers=1`
- `valid_ks_doc_id=25`
- `missing_ks_doc_id=0`
- `ks_doc_id_not_in_ks=0`

This proves Deliverable A linkage is present for one paper. It does not prove
Deliverable B is operational because the query embedding model is not available
fast enough/offline in the default environment.

## Snippet Sanitation

PASS. The focused sanitizer suite reports `31 passed in 3.61s`. The reviewed
sanitizer strips known Marker tags, page anchors, orphaned page-anchor fragments,
and inline markdown heading markers without mutating stored KS claim text.

## Findings

### Blocking: default query still hangs when model assets are absent

`_open_chroma_collection()` now fast-fails on missing collection, but once
`academic_papers` exists, `_query_chroma_semantic()` initializes
`SentenceTransformerEmbedder()` before lexical fallback. In this environment,
that repeatedly tries Hugging Face and all default acceptance queries time out
after 120s.

### Blocking: fake semantic acceptance tests are not actually offline-safe

The fake collection is injected at `tests/test_research_query.py:976-979`, but
the implementation still tries to construct the real embedder first. The first
fake-Chroma acceptance test times out after 120s, so the test plan does not pass.

### Blocking: unrelated semantic hits are not honestly rejected

The spec acceptance case expects `weather forecast` to return
`had_fallback=True` with no citations. The current semantic-first path returns
any Chroma nearest neighbor when embeddings are usable; the prior implementation
log even classifies weather as PASS with `retrieval_mode=semantic`,
`had_fallback=false`, and low `paper_score=0.0`. That is not an honest pass for
the acceptance criterion.

## Scope

No GPU parsing, 3-paper sample, 29-paper validation, SVM enforce, Marker parser
changes, benchmark baseline changes, or implementation edits were performed.

## L2.1 Status

L2.1 is not complete.

The 3-paper sample is not safe next. The single-paper/default query path still
times out when the Chroma collection exists but the embedding model is absent,
and the weather-control case is not honestly rejected by the current semantic
nearest-neighbor behavior.

## Required Next Fix

Make semantic query embedding fail fast before Hugging Face retries, and keep
lexical fallback available when the model is absent. Then add/adjust tests so
fake Chroma does not instantiate the real embedder. Finally, add a relevance
threshold or equivalent rejection rule so unrelated semantic nearest-neighbor
hits do not satisfy `weather forecast`.
