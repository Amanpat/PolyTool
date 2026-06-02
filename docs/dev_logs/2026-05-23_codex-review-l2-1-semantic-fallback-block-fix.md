# Codex Review - L2.1 Semantic Fallback Block Fix

**Date:** 2026-05-23
**Reviewer:** Codex
**Verdict:** BLOCK

## Objective

Review the L2.1 Deliverable B block fix. Done means the live academic query path
actually uses semantic retrieval, `academic_papers` Chroma linkage is usable,
acceptance tests pass without xfail, snippets remain sanitized, and L2.1 can be
declared complete or left blocked with exact reasons.

## Files reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-semantic-fallback-block-fix.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-semantic-fallback.md`
- `packages/research/synthesis/academic_query.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_query.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_research_query.py`
- `tests/test_ris_marker_queue.py`

Dirty tree note: the worktree contains many unrelated Obsidian/vault changes
plus RIS L2.1 implementation changes. I did not modify implementation code,
tests, parser/queue behavior, SVM enforce, benchmark baselines, or artifacts.
Only this review log was added.

## Diff and implementation evidence

Deliverable B was implemented in `packages/research/synthesis/academic_query.py`,
not just Deliverable A repeated:

- `AcademicQueryResult` now exposes `retrieval_mode`.
- `_open_chroma_collection()` opens the `academic_papers` Chroma collection.
- `_query_chroma_semantic()` queries Chroma and reads `ks_doc_id` metadata.
- `query_academic_corpus()` calls `_open_chroma_collection()` in the live path,
  then resolves each semantic hit through `ks.get_source_document(ks_doc_id)`.
- `tools/cli/research_query.py` includes `retrieval_mode` in JSON output.

Deliverable A linkage also exists:

- `packages/research/ingestion/marker_queue.py` defines
  `_ACADEMIC_CHROMA_COLLECTION = "academic_papers"`.
- Chroma metadata includes `ks_doc_id`, `arxiv_id`, `body_source`,
  `source_family`, `title`, `candidate_id`, and `chunk_index`.
- `tools/cli/research_marker_queue.py check-chroma-links --json` validates
  missing `ks_doc_id` and `ks_doc_id` values not present in the KnowledgeStore.

Important deviation: the implemented query path is semantic-first, not the
spec's fallback-only path. That is intentional per the implementation dev log
to avoid `LLM` substring false positives such as `Bellman`, but it is still a
spec deviation that should be accepted or revised by the operator.

## Blocking findings

### Blocking: live query path attempts Hugging Face/model loading before collection availability is known

`_open_chroma_collection()` constructs
`SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5")`
before `client.get_collection(name="academic_papers", ...)` can fail fast for a
missing collection. In this local environment, every `research-query` command
attempted network calls to `huggingface.co` and timed out at 120s.

This violates the spec requirement that absent or empty `academic_papers` be
silently skipped with the same lexical/had_fallback behavior as before. It also
makes the acceptance smokes impossible to run through the live CLI.

### Blocking: `tests/test_research_query.py` no longer completes

`python -m pytest tests/test_research_query.py -q --tb=short` timed out after
120s. A narrowed run with `-vv -x` timed out after 180s on the first test:

```text
tests/test_research_query.py::TestQueryAcademicCorpus::test_empty_ks_returns_fallback
```

Root cause from inspection: `query_academic_corpus()` opens real Chroma even
when `_store` is an in-memory test KnowledgeStore and no `_chroma_collection`
is injected. That test path should stay offline and deterministic.

### Blocking: `academic_papers` linkage is not usable locally

`python -m polytool research-marker-queue check-chroma-links --json` returned:

```text
{"error": "Collection [academic_papers] does not exist", "collection": "academic_papers", "hint": "Run 'index-done --reindex-chroma' to populate the collection first.", "exit_code": 1}
```

The command contract exists, but the local collection is absent. Combined with
the live query bug above, the system cannot currently prove semantic retrieval
against the real corpus.

## Acceptance case results

| Case | Result | Verdict |
|---|---|---|
| `LLM` | Timed out after 120s while retrying Hugging Face HEAD requests for `BAAI/bge-large-en-v1.5`. | FAIL |
| `language model financial prediction` | Timed out after 120s while retrying Hugging Face HEAD requests. | FAIL |
| `what does this paper say about hallucination` | Timed out after 120s while retrying Hugging Face HEAD requests. | FAIL |
| `weather forecast` | Timed out after 120s while retrying Hugging Face HEAD requests. | FAIL |
| Snippet sanitation | Unit-level sanitation logic exists for inline headings and orphaned `(#pag...` anchors, but live CLI output could not be reached. | NOT PROVEN |

Representative timeout output:

```text
MaxRetryError(... HTTPSConnectionPool(host='huggingface.co', port=443) ...)
Retrying in 1s [Retry 1/5].
...
command timed out after 120403 milliseconds
```

## Retrieval mode evidence

- `AcademicQueryResult.retrieval_mode` is present with default `"lexical"`.
- Semantic returns set `retrieval_mode="semantic"`.
- `tools/cli/research_query.py` includes `retrieval_mode` in both the missing-KS
  fallback JSON and normal result JSON.
- Live retrieval mode could not be observed because CLI commands timed out
  before producing JSON.

## Commands run

`git status --short`

Result: dirty worktree with unrelated Obsidian/vault changes and RIS L2.1 files
modified. I did not revert or overwrite them.

`git log --oneline -5`

```text
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
```

`python -m polytool --help`

Result: exit 0; CLI loaded and listed `research-query` and
`research-marker-queue`.

`python -m pytest tests/test_research_query.py -q --tb=short`

Result: timed out after 120s; collected 90 items and did not complete.

`python -m pytest tests/test_research_query.py -vv -x --tb=short`

Result: timed out after 180s on
`TestQueryAcademicCorpus::test_empty_ks_returns_fallback`.

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

```text
204 passed, 1 skipped in 252.26s (0:04:12)
```

`python -m polytool research-marker-queue check-chroma-links --json`

Result: exit 1; collection `academic_papers` does not exist.

`rg "pytest.mark.xfail|@pytest.mark.xfail|xfail\(" tests/test_research_query.py`

Result: exit 1 with no matches. The prior xfail markers appear removed, though
the class docstring still says the tests are intentionally xfailed.

`python -m polytool research-query --question "LLM"`

Result: timed out after 120s with Hugging Face retry output.

`python -m polytool research-query --question "language model financial prediction"`

Result: timed out after 120s with Hugging Face retry output.

`python -m polytool research-query --question "what does this paper say about hallucination"`

Result: timed out after 120s with Hugging Face retry output.

`python -m polytool research-query --question "weather forecast"`

Result: timed out after 120s with Hugging Face retry output.

## Scope violations

No new scope violation by this review. The implementation under review did not
touch SVM enforce, benchmark baselines, full 29-paper artifacts, or GPU parsing
during this review. I did not run a 3-paper sample or 29-paper validation.

## Verdict

BLOCK.

L2.1 cannot be declared complete. Semantic retrieval code is present in the live
academic query path, and `ks_doc_id` linkage machinery exists, but the live path
is not operational because Chroma/model initialization is attempted before
collection availability is safely checked. Acceptance tests and live smokes do
not pass.

A 3-paper category sample is not safe next. The safe next step is a small fix to
make Chroma collection availability fail fast without loading/downloading the
embedding model, and to keep unit tests offline unless `_chroma_collection` or an
explicit real-Chroma option is provided. Then rerun the same acceptance smokes
and `check-chroma-links`.
