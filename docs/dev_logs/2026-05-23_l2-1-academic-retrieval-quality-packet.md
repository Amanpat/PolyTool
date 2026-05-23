# L2.1 Academic Retrieval Quality — Work Packet Planning Session

**Date:** 2026-05-23
**Track:** RIS L2.1 — Academic Retrieval Quality
**Type:** Planning only — no code changed
**Spec:** `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`

---

## Objective

Draft a scoped implementation plan for RIS L2.1: semantic retrieval fallback, Chroma
doc_id linkage for academic bodies, and operator snippet sanitation. No code was changed
in this session.

---

## Context Read

Files read to inform this packet:

- `CLAUDE.md` — project conventions
- `docs/CURRENT_STATE.md` — L2.1 ChromaDB academic retrieval listed as deferred
- `docs/CURRENT_DEVELOPMENT.md` — L2.1 not in active feature slot
- `docs/features/FEATURE-ris-l2-academic-query.md` — L2 feature doc; ChromaDB path
  explicitly deferred with comment in code
- `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md` — one-paper probe
  establishing current retrieval failure taxonomy and snippet quality issues
- `docs/dev_logs/2026-05-23_codex-review-academic-speed-and-retrieval-plan.md` — Codex
  independent review confirming retrieval is not demo-ready and recommending L2.1 work
- `packages/research/synthesis/academic_query.py` — full read; core L2 implementation
- `packages/research/ingestion/retriever.py` — substring match core
- `packages/polymarket/rag/knowledge_store.py` — KS doc_id scheme
- `packages/polymarket/rag/metadata.py` — Chroma doc_id scheme (different from KS)

---

## Current Retrieval Failures

Identified from one-paper probe against arxiv:2510.05533 (34 chunks, 167 claims):

| Failure class | Example query | Root cause |
|---|---|---|
| Abbreviation blindness | `LLM` → 0 targeted hits | Claims say "Large Language Models" not "LLM" |
| Multi-word conjunction | `language model financial prediction` → 0 hits | 4-word phrase not contiguous in any claim |
| Conversational preamble | `what does this paper say about hallucination` | Preamble stripped but multi-word still fails |
| HTML artifacts in snippets | `<sup>∗</sup>`, `(#page-18-0)`, `#### **Abstract**` | Marker OCR artifacts reach operator output |

Note from Codex review: the one-paper dev log states `LLM → had_fallback=True` but the
current CLI returns `had_fallback=false` with 21 claims (substring matches "LLM" inside
unrelated words like "Bellman"). The underlying issue remains — abbreviation queries
return noisy results rather than targeted paper-body hits. The failure mode is wrong
precision, not zero recall.

---

## Proposed Deliverables

Full detail in `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`.

### Deliverable C — Operator Snippet Sanitation (first, ~1 hour)

Add `_sanitize_snippet(text: str) -> str` in `academic_query.py`. Called at render time
when building `AcademicCitation.best_snippet`. Strips HTML tags, Markdown headings,
internal page cross-refs, and excess whitespace. Raw `claim_text` in KS is not modified.

Patterns:
```python
_HTML_TAG     = re.compile(r"<[^>]+>")
_MD_HEADING   = re.compile(r"^#{1,6}\s*\*?\*?", re.MULTILINE)
_PAGE_REF     = re.compile(r"\(#page-\d+-\d+\)")
_EXTRA_SPACE  = re.compile(r"\s{3,}")
```

Risk: HTML regex could strip `<` / `>` from math expressions. Reviewer should check
actual claims from arxiv:2510.05533 before finalizing; narrow to known Marker tags if
math brackets appear.

### Deliverable A — Chroma doc_id Linkage for Academic Bodies (second, ~2 hours)

Extend `research-marker-queue index-done` to embed and upsert academic paper body text
into a new ChromaDB collection `"academic_papers"` (separate from general `"kb_rag"`).

For each indexed paper:
1. Read body from `bodies/{candidate_id}.body.txt`.
2. Split into overlapping windows (~512 tokens, ~128 overlap).
3. Embed with BAAI/bge-large-en-v1.5 (already in Docker).
4. Upsert into `academic_papers` with metadata: `ks_doc_id`, `arxiv_id`, `body_source`,
   `source_family`, `title`, `candidate_id`.

Chunk IDs: deterministic from `ks_doc_id + chunk_index` → idempotent re-runs.

Backfill: `index-done --reindex-chroma` flag to re-process already-done items with body
sidecars. Required for arxiv:2510.05533.

### Deliverable B — Semantic Retrieval Fallback (third, ~1.5 hours)

Add `_query_chroma_academic()` in `academic_query.py`. Wire into `query_academic_corpus()`
as a fallback path: fires only when substring search returns zero claims AND
`academic_papers` collection exists and is non-empty.

```
primary: KS substring (existing, unchanged)
  → if claims found: return as today
  → if no claims AND academic_papers collection exists:
      embed query, search academic_papers collection
      filter to body_source=marker chunks
      join ks_doc_id → KS source_documents
      build citations from semantic hits
```

Conservative start: fallback-only (not hybrid). Hybrid RRF merge deferred to L2.2.

---

## Acceptance Tests

| # | Command | Expected |
|---|---|---|
| AT-1 | `research-query --question "LLM"` | Returns arxiv:2510.05533; `had_fallback=False`; `claim_count >= 5` |
| AT-2 | `research-query --question "language model financial prediction"` | Returns arxiv:2510.05533; `had_fallback=False` |
| AT-3 | `research-query --question "what does this paper say about hallucination"` | Returns arxiv:2510.05533; `had_fallback=False` |
| AT-4 | `research-query --question "weather forecast"` | `had_fallback=True`; no citations |
| AT-5 | Inspect `best_snippet` in any citation from AT-1 to AT-3 | No `<sup>`, `<br>`, `####`, or `(#page-N-M)` |

AT-1 and AT-2: can pass via semantic fallback (Deliverable B).
AT-3: passes after preamble stripping + semantic fallback.
AT-4: control — must remain correctly rejected.
AT-5: Deliverable C only; independent of A and B.

---

## Smoke Protocol

All acceptance tests run against a single already-indexed paper:
- arxiv:2510.05533 ("The New Quant: A Survey of LLMs in Financial Prediction")
- KS doc_id: `987d4883...` (64-char SHA256)
- 34 chunks, 167 claims, `body_source=marker`, `body_length=93720`
- Body sidecar: verify `bodies/<candidate_id>.body.txt` exists before starting A

For A+B: confirm `academic_papers` collection is non-empty before running AT-1 to AT-3.

---

## Open Questions

1. **Embedding path for backfill**: BAAI/bge-large-en-v1.5 inside Docker GPU is
   fastest. CPU path is functional but ~500ms/query. Confirm which path the implementer
   will use before starting A. Document the choice in the closeout dev log.

2. **Snippet regex scope**: Does arxiv:2510.05533's claim text contain `<` or `>` in
   math expressions? If yes, narrow `_HTML_TAG` to known Marker tags only (`<sup>`,
   `<sub>`, `<br>`, `<br/>`). Check actual claim rows before committing C.

3. **`had_fallback` flag semantics**: Currently `had_fallback=True` means "substring
   returned zero, and no Chroma collection was available to fall back to." After B ships,
   the same flag must mean "substring returned zero, semantic fallback ran and may or
   may not have found results." Consider whether a separate `used_semantic_fallback` flag
   would be clearer, or whether updating `had_fallback=False` when semantic hits are
   found is sufficient for AT-1 to AT-3.

4. **Collection name collision (R4)**: Document `academic_papers` collection name in
   `docs/ARCHITECTURE.md` to prevent future general-RAG expansion from reusing it.

5. **Hybrid vs fallback-only for B**: Fallback-only is the conservative first pass.
   If the one-paper smoke shows that semantic-only queries (AT-1 to AT-3) succeed but
   at lower precision than expected, the implementer should note this and flag L2.2
   hybrid work rather than expanding scope mid-session.

---

## Non-Goals

- No LLM answer synthesis
- No page-level citation numbers
- No SVM enforce (remains dry-run per 2026-05-07 Director decision)
- No broad ingestion changes
- No `paper_score` query-relevance overhaul (W4; separate future item)
- No changes to `benchmark_v1`, Gate 2, or Gate 3 language
- No hybrid RRF merge (L2.2)

---

## Files Expected to Change (at implementation time)

| File | Change |
|---|---|
| `packages/research/synthesis/academic_query.py` | `_sanitize_snippet()` (C); `_query_chroma_academic()` + fallback wire (B) |
| `packages/research/ingestion/marker_queue.py` or `tools/cli/research_marker_queue.py` | `index-done --reindex-chroma` (A) |
| `tests/test_research_query.py` | Snippet sanitation tests (C); semantic fallback path tests (B) |
| `docs/ARCHITECTURE.md` | Add `academic_papers` Chroma collection entry (R4) |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Document `--reindex-chroma` flag |

---

## Files Changed in This Session

```
docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md   ← new; work packet spec
docs/dev_logs/2026-05-23_l2-1-academic-retrieval-quality-packet.md  ← this file
```

No code changed. No tests modified. No benchmark artifacts touched.

---

## Codex Review

Not required — docs-only session, no code changed.
