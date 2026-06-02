# Codex Review - L2.1 Deliverable B Semantic Fallback/Merge

**Date:** 2026-05-23
**Reviewer:** Codex
**Verdict:** BLOCK

## Objective

Review and test L2.1 Deliverable B semantic fallback/merge. Done means semantic
retrieval works for the documented failed queries, lexical-first behavior is
preserved where appropriate, semantic hits resolve through valid `ks_doc_id`,
unrelated queries stay rejected, snippets are sanitized, no LLM synthesis was
added, and L2.1 can be classified as complete or still blocked.

## Files reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md`
- `docs/dev_logs/2026-05-23_l2-1-chroma-linkage-command-contract-fix.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md`
- `packages/research/synthesis/academic_query.py`
- `tools/cli/research_query.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_research_query.py`
- `tests/test_ris_marker_queue.py`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

Requested file `docs/dev_logs/2026-05-23_l2-1-semantic-fallback.md` does not
exist in this worktree.

Dirty tree note: this worktree already had unrelated Obsidian/vault changes and
pre-existing L2.1 Deliverable A linkage changes. I did not modify implementation
code or vault files.

## Tests added or changed

Updated `tests/test_research_query.py` with `TestSemanticRetrievalAcceptanceGaps`:

- `test_abbreviation_query_llm_finds_large_language_model_paper_not_bellman`
- `test_multi_word_query_language_model_financial_prediction_returns_paper`
- `test_conversational_hallucination_query_returns_paper`
- `test_unrelated_weather_query_stays_rejected`
- `test_result_exposes_retrieval_mode_metadata`

The three semantic-positive cases and the retrieval-mode metadata case are marked
`xfail(strict=True)` because Deliverable B is not implemented. The unrelated
weather control is an ordinary passing regression test.

## Review findings

### Blocking: no semantic fallback/merge exists

`packages/research/synthesis/academic_query.py` still states that it does not
query ChromaDB, and there is no `_query_chroma_academic`, `academic_papers`
query, `ks_doc_id` join, `semantic_fallback` angle, or retrieval mode metadata in
`query_academic_corpus()` or `research-query` output.

### Blocking: `academic_papers` collection is absent locally

`research-marker-queue check-chroma-links --json` returned:

```text
{"error": "Collection [academic_papers] does not exist", "collection": "academic_papers", "hint": "Run 'index-done --reindex-chroma' to populate the collection first.", "exit_code": 1}
```

This means semantic retrieval cannot be proven in the current local state even
if query code existed.

### Blocking: documented failed queries still fail or return lexical false positives

Local `research-query` smoke results:

| Case | Result |
|---|---|
| `LLM` | `had_fallback=false`, but first result is unrelated Bellman-equation paper; target paper is second. This is a lexical substring false positive, not semantic retrieval. |
| `language model financial prediction` | `had_fallback=true`, 0 citations. |
| `what does this paper say about hallucination` | `had_fallback=true`, 0 citations. |
| `weather forecast` | `had_fallback=true`, 0 citations. Correct rejection. |

The `LLM` result is especially important: fallback-only semantic search will not
run if lexical substring hits inside words such as `Bellman` are treated as real
matches. Deliverable B needs either safer lexical token matching or semantic
merge/rerank behavior for abbreviation queries.

### Blocking: snippets are not fully sanitized in real CLI output

Existing sanitizer unit tests pass, but live CLI output still surfaced Marker
artifacts:

```text
"best_snippet": ": A Survey of Large Language Models in Financial Prediction and Trading Weilong Fu* #### **Abstract** Large language models..."
```

The `LLM` smoke also surfaced a truncated internal page anchor:

```text
"DISC FinLLM ... [2023b\\)], DISC FinLLM ... [2023\\)](#pag..."
```

Root cause from inspection: `query_knowledge_store_for_rrf()` truncates
`claim_text[:400]` before `AcademicCitation.best_snippet` sanitization. Once an
anchor is truncated to `(#pag...`, the full `(#page-N-M)` regex cannot remove it;
and markdown heading markers can appear mid-snippet rather than at line start.

### Non-blocking: no parser, ingestion, SVM, benchmark, or LLM synthesis scope leaked into my changes

I only changed tests plus this review log. Pre-existing dirty implementation
changes are Deliverable A Chroma linkage and marker-queue CLI/runbook wiring.
No GPU parsing, Marker parser changes, SVM enforce, benchmark baseline changes,
or 29-paper artifacts were run or edited by this review.

No LLM synthesis was added. Grep over the relevant query and marker files found
only deterministic query planning with `provider_name="manual"` and no OpenAI,
chat/completion, Gemini, DeepSeek, or Ollama calls in the query path.

## Commands run and output

`git status --short`

Output: dirty worktree with pre-existing changes in `AGENTS.md`, `claude.md`,
many `docs/obsidian-vault/**` files, `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`,
`packages/research/ingestion/marker_queue.py`, `tools/cli/research_marker_queue.py`,
`tests/test_ris_marker_queue.py`, and untracked L2.1 Chroma linkage dev logs.

`git log --oneline -5`

```text
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
```

`python -m polytool --help`

Output: exit 0; CLI loaded and listed `research-query` and
`research-marker-queue`.

`python -m pytest tests/test_research_query.py -q --tb=short`

```text
collected 88 items
84 passed, 4 xfailed in 1.49s
```

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

```text
collected 205 items
204 passed, 1 skipped in 3.89s
```

`python -m polytool research-marker-queue check-chroma-links --json`

```text
{"error": "Collection [academic_papers] does not exist", "collection": "academic_papers", "hint": "Run 'index-done --reindex-chroma' to populate the collection first.", "exit_code": 1}
```

`python -m polytool research-query --question "LLM"`

```text
had_fallback=false
total_claims_found=21
citations=4
first citation="Closed-form approximations in multi-asset market making" (arxiv:1810.04383)
target citation="The New Quant: A Survey of Large Language Models in Financial Prediction and Trading" (arxiv:2510.05533), rank=2, claim_count=11
```

`python -m polytool research-query --question "language model financial prediction"`

```text
had_fallback=true
total_claims_found=0
citations=0
```

`python -m polytool research-query --question "what does this paper say about hallucination"`

```text
had_fallback=true
total_claims_found=0
citations=0
```

`python -m polytool research-query --question "weather forecast"`

```text
had_fallback=true
total_claims_found=0
citations=0
```

`python -m polytool research-query --question "language model"`

```text
had_fallback=false
citations=1
best_snippet contains "#### **Abstract**"
```

## Acceptance case results

| Acceptance case | Result | Verdict |
|---|---|---|
| AT-1 `LLM` returns arxiv:2510.05533 with `had_fallback=false` and `claim_count >= 5` | Target paper appears at rank 2 with 11 claims, but rank 1 is unrelated Bellman false positive; no semantic mode exists. | FAIL |
| AT-2 `language model financial prediction` returns arxiv:2510.05533 | 0 citations. | FAIL |
| AT-3 conversational hallucination query returns arxiv:2510.05533 | 0 citations. | FAIL |
| AT-4 `weather forecast` stays rejected | 0 citations, `had_fallback=true`. | PASS |
| AT-5 snippets have no Marker artifacts | Live output still contains `#### **Abstract**` and truncated `(#pag...` artifact. | FAIL |
| Semantic hits resolve through valid `ks_doc_id` | Cannot verify: no semantic query path and no local `academic_papers` collection. | FAIL |
| Lexical-first behavior preserved | Lexical path is still first, but abbreviation lexical false positives block semantic fallback. | FAIL for acceptance |
| Retrieval mode field/metadata present | No field in dataclass or CLI JSON. | FAIL |

## Scope violations

No new scope violation was introduced by this review. The blocker is absence of
Deliverable B, not scope creep. The pre-existing dirty L2.1 changes are confined
to Deliverable A Chroma linkage and runbook/tests.

## Verdict

BLOCK.

L2.1 is not complete. Deliverable C is also not fully proven in live CLI output,
and Deliverable B is absent. A 3-paper category sample is not safe next because
the one-paper acceptance cases still fail and the semantic collection is not
available locally.

## Recommended next action

1. Populate and verify `academic_papers` for the smoke paper with
   `research-marker-queue index-done --reindex-chroma --force` and
   `research-marker-queue check-chroma-links --json`.
2. Implement Deliverable B in `query_academic_corpus()` with a test-injectable
   Chroma query path, `ks_doc_id` join validation, `body_source=marker` filter,
   and explicit retrieval mode metadata.
3. Do not rely on fallback-only for `LLM` until lexical substring false positives
   are fixed or semantic merge/rerank is added.
4. Fix snippet sanitation on raw claim text before truncation, or sanitize partial
   page-anchor artifacts after truncation, then rerun AT-1 through AT-5.
