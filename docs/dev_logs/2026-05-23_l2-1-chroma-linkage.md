# L2.1 Deliverable A — ChromaDB Academic Collection Linkage

**Date:** 2026-05-23
**Status:** CLOSED — implementation + tests complete

## Objective

Link academic KnowledgeStore documents to a dedicated ChromaDB `academic_papers`
collection using a stable `ks_doc_id` stored in each chunk's metadata.  This makes
every Chroma chunk traceable back to its source document without a separate index.

## Scope

- `packages/research/ingestion/marker_queue.py`
  - `_ACADEMIC_CHROMA_COLLECTION = "academic_papers"` constant
  - `_embed_body_into_chroma()` — chunks body, generates deterministic chunk IDs from
    `sha256(ks_doc_id + "\x00" + chunk_index)`, upserts into the named collection with
    full metadata including `ks_doc_id`, `arxiv_id`, `body_source`, `source_family`,
    `title`, `candidate_id`, `chunk_index`
  - `index_done_items(embed_chroma=True)` — embeds into Chroma after KS indexing (non-fatal)
  - `embed_done_items_into_chroma()` — standalone backfill; reads `indexed.jsonl`,
    tracks already-embedded items in `chroma_embedded.jsonl`
- `tools/cli/research_marker_queue.py`
  - `index-done --reindex-chroma` flag wired through to `embed_chroma=True`
  - `index-done --chroma-path PATH` for custom Chroma directory
  - `check-chroma-links` subcommand: opens `academic_papers`, reports total chunks,
    unique papers, missing `ks_doc_id`, and `ks_doc_id` values not found in KS
- `tests/test_ris_marker_queue.py`
  - `_FakeChromaCollection`, `_FakeChromaClient`, `_FakeChromaModule`, `_FakeEmbedder`
    stubs — zero dep, fully offline
  - `TestEmbedBodyIntoChroma` — 9 tests for `_embed_body_into_chroma()`
  - `TestEmbedDoneItemsIntoChroma` — 7 tests for `embed_done_items_into_chroma()`
  - `TestCLICheckChromaLinks` — 8 tests for `check-chroma-links` CLI

## Negative scope

No changes to:
- Semantic retrieval / academic_query.py query path
- Marker parser / queue operation
- Snippet sanitation (Deliverable C, already shipped)
- SVM enforce, benchmark baselines, full 29-paper artifacts

## Key design decisions

- **Deterministic chunk IDs**: `sha256(ks_doc_id + "\x00" + i)` means re-running
  `embed_done_items_into_chroma()` or `index-done --reindex-chroma` is always a
  safe no-op (Chroma upsert overwrites by ID).
- **Separate collection**: `academic_papers` is separate from `polytool_rag` so
  academic semantic search can filter by `body_source` and `ks_doc_id` metadata
  without touching the general knowledge graph.
- **Non-fatal embedding**: Chroma errors during `index-done` are logged as warnings;
  the KS index succeeds regardless. Backfill via `embed_done_items_into_chroma()`
  can repair any partial state.
- **`chroma_embedded.jsonl`**: Analogous idempotency file to `indexed.jsonl`.

## Test results

```
tests/test_ris_marker_queue.py::TestEmbedBodyIntoChroma       9/9 passed
tests/test_ris_marker_queue.py::TestEmbedDoneItemsIntoChroma  7/7 passed
tests/test_ris_marker_queue.py::TestCLICheckChromaLinks       8/8 passed
Full suite: 201 passed, 1 skipped in 3.54s
```

## Verification commands (smoke corpus — after real Chroma populated)

```bash
# Backfill: embed all already-indexed items
python -m polytool research-marker-queue embed-chroma

# Check linkage health
python -m polytool research-marker-queue check-chroma-links --json

# Expected clean output:
#   missing_ks_doc_id: 0
#   ks_doc_id_not_in_ks: 0
```

## Codex review

Scope: no execution, kill-switch, rate-limiter, or order-placement code touched.
Codex review not required per CLAUDE.md policy (docs + tests + queue helper only).
