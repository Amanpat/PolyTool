---
tags: [architecture, ris, scientific-rag, target-state]
date: 2026-04-27
status: target-design
source: "[[Decision - Scientific RAG Architecture Adoption]]"
---

# 11 — Scientific RAG Target Architecture

The target-state design for the RIS academic pipeline, synthesized from the GLM-5 survey's "concrete combination" and locked in by [[Decision - Scientific RAG Architecture Adoption]]. Layer 0 has shipped. Layer 1 scaffold is implemented as an experimental opt-in. Layers 2–4 are future packets. Each layer is a separate work packet built in order.

Full survey backing this design: [[11-Scientific-RAG-Pipeline-Survey]].

---

## The four layers

Stacked bottom-up. Each layer assumes the layer below it works.

### Layer 0 — Foundation (shipped)

**Status:** shipped 2026-04-27. See [[Work-Packet - Academic Pipeline PDF Download Fix]] (status: shipped).

`LiveAcademicFetcher` now downloads arXiv PDFs via pdfplumber and populates `body_text` with full paper content. Live validation: `body_source=pdf`, `body_length=58927`, `chunk_count=27` confirmed end-to-end including Docker. 54 tests passing. pdfplumber 0.11.9 in `ris` optional group.

This layer is the foundation everything else builds on. Without it, the academic pipeline was silently shallow; with it, the pipeline ingests real paper bodies even before structural parsing arrives.

### Layer 1 — Structural parser

**Status:** scaffold implemented 2026-04-27 — experimental opt-in, production rollout deferred. See [[Work-Packet - Marker Structural Parser Integration]] and `docs/features/ris-marker-structural-parser-scaffold.md`.

`MarkerPDFExtractor` is wired alongside pdfplumber. **pdfplumber remains the default parser** — Marker is explicit opt-in only via `RIS_PDF_PARSER=auto` or `RIS_PDF_PARSER=marker`. CPU Marker timed out at 300 s for all tested papers; GPU required for production throughput. Production rollout is deferred pending GPU host availability.

When Marker succeeds, output goes into the same `body_text` field as structured Markdown/JSON, with structural markers downstream layers can use:

- Section boundaries become candidate chunk boundaries (instead of fixed-size chunks)
- LaTeX equations survive the embedding step intact (instead of being mangled by PDF text extraction)
- Tables retain row/column structure (instead of being concatenated cell-by-cell)
- Page numbers and bounding boxes attach to every element (precise source handles)

pdfplumber stays as fallback for CPU-only environments, large PDFs that exceed Marker's memory budget, or when Marker fails on a specific document. The `body_source` metadata field includes `"marker"`, `"pdfplumber_fallback"`, and `"abstract_fallback"`. There is no `"marker_llm_boost"` value — LLM-enriched extraction is not wired; `RIS_MARKER_LLM=1` sets `marker_llm_requested=True`, `marker_llm_applied=False` only. That is a Layer 2 deliverable.

License posture: Marker is GPL-3.0 + modified Open Rail-M. PolyTool RIS is treated as personal/research tooling under that license. Revisit if commercial deployment changes the posture.

### Layer 2 — RAG control flow

**Status:** future packet (see [[Work-Packet - PaperQA2 RAG Control Flow]]).

The current retrieval flow is a single ChromaDB similarity search plus an SQLite FTS5 keyword search, fused. That's adequate for short docs; for full papers it loses to PaperQA2's agentic approach, which:

1. Receives a query
2. Searches paper-level index for candidate papers (5-10)
3. For each candidate, retrieves top-K chunks
4. Re-ranks chunks against the query
5. Runs Recursive Contextual Summarization (RCS) — chunk + neighboring context summarized into a search result with citation
6. Synthesizes answer from top results, with in-text citations mapping to specific page/section

We adopt this control flow but keep ChromaDB + SQLite FTS5 as the storage layer. Embeddings remain SentenceTransformers (Tier 1 free, no OpenAI dependency). LLM steps (re-ranking, RCS, synthesis) route to Gemini Flash via our existing provider layer.

The deliverable is a new `polytool research-query` command that takes a question and returns answers with citations to specific PDF pages, replacing the current naïve `rag-query`.

### Layer 3 — Pre-fetch relevance filter

**Status:** future packet (see [[Work-Packet - Pre-fetch SVM Topic Filter]]).

Without a pre-filter, every paper that hits the academic pipeline burns Gemini quota and ChromaDB storage. Most papers found by multi-source harvesters (Layer 4) are not relevant to market microstructure / prediction markets / quantitative finance. The eval gate is too expensive to use as a relevance filter.

Layer 3 inserts a cheap pre-fetch decision step before the LLM gate:

1. Get paper metadata (title, abstract, fields-of-study) — from Semantic Scholar API or arXiv Atom API
2. Compute SPECTER2 embedding of (title + abstract)
3. Compute S2FOS field-of-study labels
4. Score against a domain-specific SVM trained on operator-curated positive examples (papers we kept) and negative examples (papers we rejected)
5. Above threshold → proceed to fetch + parse + LLM gate. Below threshold → skip.

Training data accumulates as the operator runs the YELLOW review queue. Each accept/reject decision is a labeled example. The SVM retrains nightly. Cold-start uses a small seed set of 20-50 hand-picked positive examples (Avellaneda-Stoikov, Kelly, the Jon-Becker findings, the seeded foundational papers) and a similar number of off-topic negatives.

This is the layer that makes multi-source ingestion (Layer 4) viable. Without Layer 3, increasing Layer 4's volume linearly increases Gemini quota burn.

### Layer 4 — Multi-source harvesters

**Status:** future packet (see [[Work-Packet - Multi-source Academic Harvesters]]).

The current pipeline reaches arXiv only. Layer 4 adds:

- **Semantic Scholar API** as the primary metadata + PDF-URL aggregator. Covers most publishers and preprint servers under one rate-limited API.
- **SSRN scraper** with explicit session/cookie/redirect handling. Critical for finance/econ working papers.
- **NBER scraper** with working-group filtering. Covers macro/finance research not in Semantic Scholar's coverage gaps.
- **OpenReview** for ML/CS conferences (NeurIPS, ICLR, ICML) when relevant — most prediction-markets work is not here, but auction theory and market-design papers occasionally are.
- **Crossref / Unpaywall** for DOI resolution and open-access PDF discovery.

Layer 4 produces metadata-only candidates. Each candidate flows through Layer 3 (pre-filter) before any PDF download. PDF download then flows through Layer 1 (parser) and into the existing eval gate via Layer 0's foundation.

---

## What's deliberately not in this design

- **Late chunking and RAPTOR** are deferred. Adopt only after Layer 1's structured output gives us a chunking baseline to compare against. Premature without that.
- **ColBERTv2 / PLAID multi-vector retrieval** is skipped — infrastructure cost unjustified at our scale per the survey's "what we should not do" list.
- **Other ingestion families (reddit, blog, youtube, github)** are out of scope. Each has its own structure and would need its own diagnosis if surfacing issues.
- **Live RAG on the YELLOW review queue** — decoupled from this architecture. Operator review remains a separate workflow informed by Hermes triage (deferred).

---

## Build order and dependencies

```
Layer 0 (foundation)         ← SHIPPED 2026-04-27 (pdfplumber, full PDF body)
   ↓ produces body_text
Layer 1 (parser)             ← scaffold implemented; production rollout deferred (GPU required)
   ↓ produces structured Markdown/JSON (deferred until production rollout)
Layer 2 (RAG control flow)   ← future packet, ships after Layer 1 production rollout
   ↓ produces query → cited-answer interface
Layer 3 (pre-filter)         ← future packet, parallel-buildable with Layer 2
   ↓ produces on-topic / off-topic decision
Layer 4 (multi-source)       ← future packet, gated by Layer 3 working
```

Skipping the order produces wasted work. Layer 4 without Layer 3 floods the eval gate with off-topic papers. Layer 3 without Layer 1 trains an SVM on degraded text. Layer 2 without Layer 1 builds RCS and citation traversal on chunks that don't preserve structure.

---

## Cross-references

- [[Decision - Scientific RAG Architecture Adoption]] — the operational decision behind this design
- [[11-Scientific-RAG-Pipeline-Survey]] — the survey that informed the design
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — Layer 0 packet (shipped 2026-04-27)
- [[Work-Packet - Marker Structural Parser Integration]] — Layer 1 packet (scaffold implemented, production deferred)
- [[Work-Packet - PaperQA2 RAG Control Flow]] — Layer 2 packet (stub)
- [[Work-Packet - Pre-fetch SVM Topic Filter]] — Layer 3 packet (stub)
- [[Work-Packet - Multi-source Academic Harvesters]] — Layer 4 packet (stub)
- [[Work-Packet - Scientific RAG Evaluation Benchmark]] — evaluation packet (stub)
- [[2026-04-27 Academic Pipeline Diagnosis]] — bug that triggered this architecture
- [[RIS]] — current module
- [[RAG]] — current module
