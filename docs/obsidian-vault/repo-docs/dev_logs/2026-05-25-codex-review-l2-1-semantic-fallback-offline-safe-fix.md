---
title: Codex Review L2 1 Semantic Fallback Offline Safe Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-offline-safe-fix.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - L2.1 Semantic Fallback Offline-Safe Fix

**Date:** 2026-05-25
**Reviewer:** Codex
**Verdict:** BLOCK

## Objective

Review the L2.1 Deliverable B offline-safe semantic retrieval fix. Done means
default `research-query` cannot hang from missing model assets, fake-Chroma
tests are offline-safe, irrelevant semantic nearest-neighbor hits are rejected,
and L2.1 can be declared complete or remains blocked with exact reasons.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-25_l2-1-semantic-fallback-offline-safe-fix.md`
- `docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-fast-fail.md`
- `packages/research/synthesis/academic_query.py`
- `tools/cli/research_query.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_research_query.py`
- `tests/test_ris_marker_queue.py`

## Git Diff / Scope

`git status --short` showed a large dirty tree dominated by unrelated
`docs/obsidian-vault/` changes, plus marker queue/query files. I did not revert
or modify those files.

`git show --stat --oneline HEAD` showed commit `4788871 fix(ris): L2.1
Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK` is not
limited to offline-safe semantic retrieval. It includes 127 files and 14,961
insertions, mostly `docs/obsidian-vault/legacy/...` files. That violates the
"confirm the fix is limited" review expectation even though the functional L2.1
code path is identifiable.

## Code Review Evidence

Positive:

- `_query_chroma_semantic()` uses `SentenceTransformer(..., local_files_only=True)`
  at `packages/research/synthesis/academic_query.py:379`, so the model load does
  not request Hugging Face downloads.
- `_embed_fn` injection is wired through `query_academic_corpus()` into
  `_query_chroma_semantic()` at `academic_query.py:508`.
- Fake-Chroma acceptance tests pass `_embed_fn=lambda q: None` at
  `tests/test_research_query.py:979`, `998`, `1018`, and `1055`, so they bypass
  the real embedder.
- Low-similarity Chroma hits are discarded by `min_similarity=0.3` at
  `academic_query.py:349` and `415`.
- `check-chroma-links` verifies `ks_doc_id` linkage and cross-references the
  KnowledgeStore.

Blocking:

- The default semantic collection contains only arxiv `2604.24366`, not the L2.1
  smoke paper `2510.05533` required by the spec. Live semantic acceptance for
  "language model financial prediction" therefore returns the wrong paper.
- The default `LLM` query still ranks Bellman-related lexical substring hits
  ahead of the Large Language Models finance paper because semantic retrieval
  does not supply the target paper.
- The default hallucination query returns no citation.
- A semantic snippet from the default CLI still leaks raw Marker HTML
  (`<span id="page-...">`) and markdown links, so snippet sanitation is not
  broadly preserved on semantic output.
- `semantic_unavailable_reason` remains `null` when the model path fails fast
  and falls through to lexical, so semantic unavailability is not explicit in
  the default result metadata.

## Commands Run

`git status --short`

Result: dirty worktree with large unrelated `docs/obsidian-vault/` changes and
relevant L2.1 files. No files were reverted.

`git log --oneline -5`

```text
4788871 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
```

`python -m polytool --help`

Result: exit 0; CLI loaded and listed `research-query` and
`research-marker-queue`.

`python -m pytest tests/test_research_query.py -q --tb=short`

```text
95 passed in 4.69s
```

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

```text
204 passed, 1 skipped in 6.38s
```

`python -m pytest tests/test_research_query.py::TestSemanticRetrievalAcceptanceGaps -q --tb=short`

```text
6 passed in 3.56s
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

Chroma sample inspection:

```json
{
  "count": 25,
  "sample_arxiv_ids": ["2604.24366"],
  "sample_titles": [
    "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book"
  ]
}
```

## Timeout Verification

Simulated missing local model assets with an injected `sentence_transformers`
module whose `SentenceTransformer` raises immediately. `academic_papers` was
represented by a fake collection. Result:

```json
{
  "elapsed_seconds": 0.0908,
  "had_fallback": true,
  "citations": 0,
  "retrieval_mode": "lexical",
  "semantic_unavailable_reason": null,
  "collection_calls": [
    {
      "query_texts": ["weather forecast"],
      "n_results": 20,
      "include": ["metadatas", "distances", "documents"]
    }
  ]
}
```

Direct `_query_chroma_semantic()` probe verified the model constructor receives
`local_files_only=True` and then falls through to `query_texts=`:

```json
{
  "hits": [],
  "captured": {
    "args": ["BAAI/bge-large-en-v1.5"],
    "kwargs": {"local_files_only": true},
    "query_kwargs": {
      "query_texts": ["weather forecast"],
      "n_results": 20,
      "include": ["metadatas", "distances", "documents"]
    }
  }
}
```

Default CLI acceptance commands no longer timed out:

| Query | Wall time | Exit | Result |
|---|---:|---:|---|
| `LLM` | 39.5s | 0 | Returned citations, lexical mode |
| `language model financial prediction` | 23.3s | 0 | Returned semantic citation |
| `what does this paper say about hallucination` | 43.9s | 0 | No citation |
| `weather forecast` | 39.0s | 0 | Correct no-result |

## Acceptance Case Results

| Case | Result | Classification |
|---|---|---|
| `LLM` | `had_fallback=false`, `retrieval_mode=lexical`; returns `2510.05533` second with `claim_count=11`, but ranks Bellman papers first due substring match. | CONCERN / partial |
| `language model financial prediction` | `had_fallback=false`, `retrieval_mode=semantic`; returns `2604.24366` Anatomy of a Decentralized Prediction Market, not the required `2510.05533` New Quant paper. | FAIL |
| `what does this paper say about hallucination` | `had_fallback=true`, no citations. | FAIL |
| `weather forecast` | `had_fallback=true`, no citations. | PASS |
| fake-Chroma `LLM`, `language model financial prediction`, hallucination, low-sim weather | 6 targeted tests pass; real embedder bypassed. | PASS |

## Semantic Threshold Result

The injected low-similarity weather test passes and default `weather forecast`
is rejected. However, the live semantic threshold is still too permissive for
the default indexed corpus: `language model financial prediction` accepts
arxiv `2604.24366` at score `0.3567626476`, even though the L2.1 target is
arxiv `2510.05533`.

This means the specific weather control is fixed, but irrelevant semantic
nearest-neighbor acceptance is not fully solved.

## Snippet Sanitation

Focused sanitizer tests pass, and lexical snippets no longer show the known
`<sup>`, `<br>`, `####`, or `(#page-N-M)` patterns in the checked outputs.

The semantic `language model financial prediction` output still contains raw
Marker HTML spans and markdown links:

```text
<span id="page-14-12"></span>
[https://ar](https://arxiv.org/abs/2603.03136)
```

So display sanitation is incomplete for semantic body chunks.

## Verdict

BLOCK.

The offline-safety blocker is substantially fixed: missing model assets return
quickly, no Hugging Face download path is attempted before fallback, and
fake-Chroma tests are offline-safe. But L2.1 cannot be declared complete because
default acceptance still fails:

1. `academic_papers` is linked but populated with `2604.24366`, not the required
   smoke paper `2510.05533`.
2. `language model financial prediction` returns the wrong semantic paper.
3. `what does this paper say about hallucination` returns no citation.
4. `LLM` still surfaces Bellman lexical false positives before the LLM paper.
5. Semantic snippets can still leak raw Marker HTML.
6. The reviewed commit is not scope-clean due unrelated vault/legacy additions.

## L2.1 Status

L2.1 remains blocked.

The 3-paper sample is not safe next. First repair the one-paper L2.1 acceptance
state: ensure `academic_papers` contains the intended `2510.05533` paper (or
update the spec and acceptance target), tighten semantic relevance enough to
reject wrong-paper nearest neighbors, and sanitize semantic body snippets.
