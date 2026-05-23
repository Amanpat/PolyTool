---
status: draft
created: 2026-05-23
track: Research Intelligence System
layer: L2.1
requires_director_approval: true
---

# SPEC: RIS L2.1 — Academic Retrieval Quality

**Layer:** L2.1 (semantic retrieval + snippet quality)
**Prerequisite:** L2 complete (`docs/features/FEATURE-ris-l2-academic-query.md`)
**Implementation estimate:** 1 session (3–5 hours)
**Smoke paper:** arxiv:2510.05533 (already indexed; 34 chunks, 167 claims, `body_source=marker`)

---

## Problem Statement

`research-query` (L2) uses case-insensitive substring matching against
`claim_text` in the KnowledgeStore. This works for narrow single-token or
bigram queries ("sentiment", "temporal leakage") but fails for:

| Failure class | Example | Root cause |
|---|---|---|
| Abbreviation blindness | `LLM` → 0 targeted matches | Claims say "Large Language Models", not "LLM" |
| Multi-word conjunction | `language model financial prediction` → 0 | 4-word phrase not contiguous in any claim |
| Conversational query | `what does this paper say about hallucination` | Preamble stripped but multi-word still fails |
| HTML artifacts in snippets | `<sup>∗</sup>`, `(#page-18-0)`, `#### **Abstract**` | Marker OCR artifacts reach operator output |

One-paper probe (2026-05-23) found 9/11 substantive queries succeed on
narrow terms; all multi-word / abbreviation queries fail. Not demo-ready.

ChromaDB at `kb/rag/index/chroma.sqlite3` has 24,502 embeddings but none
are academic paper bodies — that index covers the general file-based RAG
(`kb/`, `docs/`). Academic paper bodies are in
`bodies/{candidate_id}.body.txt` (written at warm-process time) and are
not yet embedded.

---

## Non-Goals

- No LLM answer synthesis (structured citations only — unchanged from L2)
- No page-level citation guarantee (page markers in Marker output are not
  yet parsed into chunk metadata)
- No SVM enforce (remains dry-run per Director decision 2026-05-07)
- No broad ingestion changes — `IngestPipeline` Marker gate is unchanged
- No `paper_score` query-relevance overhaul (W4 from one-paper audit; a
  separate future item)
- No changes to `benchmark_v1`, Gate 2, or Gate 3 language

---

## Deliverables

### Deliverable A — Chroma doc_id Linkage for Academic Bodies

**Problem:** When academic papers are eventually indexed into ChromaDB for
semantic search, there is no stored link from a Chroma chunk back to its
KnowledgeStore `source_document.id` (64-char URL-based SHA256). Without
this link, a semantic hit cannot be joined to a KS paper for citation
output.

**Proposed change:**

Extend `research-marker-queue index-done` to also embed and upsert academic
paper body text into a dedicated ChromaDB collection named
`"academic_papers"` (separate from the existing general `"kb_rag"` or
`"default"` collection to avoid contamination).

For each paper being indexed:
1. Read body from `bodies/{candidate_id}.body.txt`.
2. Split into overlapping windows (~512 tokens, ~128 token overlap).
3. Embed with the approved model (BAAI/bge-large-en-v1.5, already in Docker).
4. Upsert into `academic_papers` collection with metadata:

```python
{
    "ks_doc_id":      "<64-char KS source_documents.id>",
    "arxiv_id":       "<e.g. 2510.05533>",
    "body_source":    "marker",
    "source_family":  "academic",
    "title":          "<paper title>",
    "candidate_id":   "<queue candidate_id>",
}
```

Chunk IDs in Chroma: deterministic from `ks_doc_id + chunk_index` to make
`index-done` idempotent on re-runs.

**Backfill for existing paper:** Run `index-done` with a `--reindex-chroma`
flag (or equivalent) to re-process already-done queue items that have a
body sidecar. This is required for arxiv:2510.05533.

**Isolation:** The `academic_papers` Chroma collection is completely
separate from the general RAG collection. No existing embeddings are
touched.

---

### Deliverable B — Semantic Retrieval Fallback in `query_academic_corpus()`

**Problem:** `query_academic_corpus()` has only a KS substring path.
Semantic/vector search via ChromaDB is not wired.

**Proposed change:** Add a fallback semantic path inside
`packages/research/synthesis/academic_query.py`:

```
primary path: KS substring (existing, unchanged)
  → if merged_claims is non-empty: return as today
  → if merged_claims is empty AND chroma_collection exists:
      run semantic query against academic_papers collection
      filter results to body_source=marker chunks
      join ks_doc_id back to KS source_documents
      build citations from semantic hits
      set had_fallback=False, add query_angles entry "semantic_fallback"
```

**Mode: fallback-only (conservative start)**

The semantic path fires only when the substring path returns zero claims.
This preserves all existing behavior for working queries and adds semantic
coverage only for the cases that currently fail.

Hybrid merge (always run both and RRF-merge) is better for recall but
riskier for a first iteration. Defer hybrid to L2.2 if fallback-only
proves insufficient.

**Chroma collection availability check:** If `academic_papers` collection
does not exist or is empty, the semantic path is silently skipped (same
`had_fallback=True` behavior as today). No hard dependency on Chroma being
present.

**Dependencies:** Requires Deliverable A to have run at least once for
the target paper(s). Embedding model must be available (Docker GPU path or
local CPU path with BAAI/bge-large-en-v1.5 downloaded).

---

### Deliverable C — Operator Snippet Sanitation

**Problem:** `best_snippet` in citation output contains Marker OCR artifacts
that appear directly in CLI output and would be passed to downstream LLM
consumers.

**Observed artifact classes:**

| Pattern | Example | Type |
|---|---|---|
| HTML tags | `<sup>∗</sup>`, `<br>` | Footnote markers |
| Markdown headings | `#### **Abstract**` | Marker section heading |
| Internal cross-refs | `(#page-18-0)` | Marker intra-doc link format |
| Raw footnote text mixed into abstract | "Work was done while the author was at JP Morgan" intermixed with abstract text | Chunking artifact |

**Proposed change:** Add `_sanitize_snippet(text: str) -> str` in
`academic_query.py`, called when building `AcademicCitation.best_snippet`:

```python
import re

_HTML_TAG = re.compile(r"<[^>]+>")
_MD_HEADING = re.compile(r"^#{1,6}\s*\*?\*?", re.MULTILINE)
_PAGE_REF = re.compile(r"\(#page-\d+-\d+\)")
_EXTRA_WHITESPACE = re.compile(r"\s{3,}")

def _sanitize_snippet(text: str) -> str:
    text = _HTML_TAG.sub("", text)
    text = _MD_HEADING.sub("", text)
    text = _PAGE_REF.sub("", text)
    text = _EXTRA_WHITESPACE.sub("  ", text)
    return text.strip()
```

**Scope:** Applied at render time only inside `query_academic_corpus()`.
The raw `claim_text` in KnowledgeStore is NOT modified. This makes the
change reversible and avoids touching ingestion.

**Side effect:** `query_knowledge_store_for_rrf()` callers that bypass
`query_academic_corpus()` will still see raw artifacts. Acceptable — those
callers are internal/test use only.

---

## Implementation Order

| Order | Deliverable | Rationale |
|---|---|---|
| 1 | C — Snippet Sanitation | Pure render-time fix, ~1 hour, immediate UX win, no infrastructure |
| 2 | A — Chroma Linkage | Infrastructure groundwork, enables B |
| 3 | B — Semantic Fallback | Requires A; wire semantic path once collection exists |

---

## Acceptance Tests

All five must pass against arxiv:2510.05533 before the packet is
declared complete.

| # | Command | Expected outcome |
|---|---|---|
| AT-1 | `research-query --question "LLM"` | Returns arxiv:2510.05533; `had_fallback=False`; `claim_count >= 5` |
| AT-2 | `research-query --question "language model financial prediction"` | Returns arxiv:2510.05533; `had_fallback=False` |
| AT-3 | `research-query --question "what does this paper say about hallucination"` | Returns arxiv:2510.05533; `had_fallback=False` |
| AT-4 | `research-query --question "weather forecast"` | `had_fallback=True`; no citations (correct rejection) |
| AT-5 | Inspect `best_snippet` in any citation from AT-1 to AT-3 | No `<sup>`, `<br>`, `####`, or `(#page-N-M)` present |

AT-1 and AT-2 can pass via the semantic fallback path (Deliverable B).
AT-3 passes after preamble stripping + semantic fallback.
AT-4 is a control — must remain rejected.
AT-5 is Deliverable C only; independent of A and B.

---

## Smoke Protocol

All acceptance tests run against the single already-indexed paper:
- arxiv:2510.05533 ("The New Quant: A Survey of LLMs in Financial Prediction")
- KS `id = 987d4883...` (64-char SHA256)
- 34 chunks, 167 claims, `body_source=marker`, `body_length=93720`
- Body sidecar: `bodies/<candidate_id>.body.txt` (verify exists before A)

For A+B: confirm `academic_papers` Chroma collection exists and has > 0
entries before running AT-1 through AT-3. If collection is empty, AT-1 to
AT-3 cannot pass via semantic fallback.

---

## Risk Notes

**R1 — Backfill requires re-running embedding inside Docker**

The existing body sidecar (`bodies/<candidate_id>.body.txt`) was written
during warm-process. Re-running `index-done --reindex-chroma` needs the
embedding model (BAAI/bge-large-en-v1.5) available. Local CPU path is slow
but functional. Docker GPU path is faster but requires the marker-worker
container to be running. Document which path is used in the dev log.

**R2 — No migration needed for existing Chroma collection**

The 24,502 embeddings in `kb/rag/index/chroma.sqlite3` are from the
general file-based RAG pipeline. The `academic_papers` collection is new
and separate. No migration or ID-alignment work is needed for existing
data.

**R3 — Semantic fallback may increase latency**

Each semantic query requires an embedding call (fast on GPU, ~50ms; slow
on CPU, ~500ms per query). Since fallback fires only on zero-match cases,
the cost is paid only when substring search fails — which is the current
failure case anyway. Net user experience: slower on currently-failing
queries, unchanged on currently-working queries.

**R4 — Collection name collision**

If the general RAG system is later extended to use `academic_papers` as a
collection name, conflicts could arise. Document the new collection name
in `docs/ARCHITECTURE.md` under the Chroma collections section.

**R5 — Snippet sanitization false positives**

The HTML-tag regex `<[^>]+>` would strip legitimate `<` / `>` in math
expressions or code if any ever appear in Marker-parsed academic claim
text. Review the regex against actual claims from arxiv:2510.05533 before
finalizing. If math brackets are present, narrow to known Marker tags only
(`<sup>`, `<sub>`, `<br>`, `<br/>`).

---

## Files Expected to Change

| File | Change |
|---|---|
| `packages/research/synthesis/academic_query.py` | Add `_sanitize_snippet()` (C); add `_query_chroma_academic()` and wire into `query_academic_corpus()` (B) |
| `packages/research/ingestion/marker_queue.py` or `tools/cli/research_marker_queue.py` | Extend `index-done` to embed and upsert into `academic_papers` Chroma collection (A) |
| `tests/test_research_query.py` | Update existing tests for snippet sanitation; add tests for semantic fallback path |
| `docs/ARCHITECTURE.md` | Add `academic_papers` Chroma collection to the Chroma collections section (R4) |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Document `--reindex-chroma` flag (A backfill step) |

---

## Out of Scope for This Packet

- Hybrid (always-on RRF merge of substring + semantic) — defer to L2.2
- Query-relevance scoring (`paper_score` proportional to claim count or BM25) — defer
- Page-level citation numbers from Marker body text — defer
- Abbreviation expansion map (`LLM → "large language model"`) — covered by
  semantic fallback; explicit expansion map is unnecessary if B ships
- Changes to `benchmark_v1`, Gate 2 thresholds, or SVM enforce
