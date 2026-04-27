---
tags: [decision]
date: 2026-04-27
status: accepted
topics: [ris, scientific-rag, architecture]
supersedes: none
source: "[[11-Scientific-RAG-Pipeline-Survey]]"
---

# Decision — Scientific RAG Architecture Adoption

## Context

The RIS academic pipeline currently ingests only abstracts (see [[2026-04-27 Academic Pipeline Diagnosis]]). The immediate fix wires pdfplumber into the existing `LiveAcademicFetcher` (see [[Work-Packet - Academic Pipeline PDF Download Fix]]). That packet ships with explicit "don't introduce GROBID/Marker/Nougat/Docling" scope discipline so it can land in one day.

The longer arc — what the academic pipeline should look like after the immediate fix — was deferred to a survey. The GLM-5 Scientific RAG Pipeline Survey ran 2026-04-27 and produced findings on 18 candidate projects. Full survey at [[11-Scientific-RAG-Pipeline-Survey]]. This decision condenses those findings into adopt/skip/defer choices that constrain all follow-up RIS work.

## Decision

Adopt a four-layer scientific RAG architecture, designed in [[11-Scientific-RAG-Target-Architecture]], built incrementally over multiple work packets. The current pdfplumber-based pipeline becomes the foundation. Each layer is a separate work packet in `12-Ideas/`.

### Adopt

1. **Parser layer — Marker (with pdfplumber fallback).** Marker provides the best balance of structure preservation, table handling, and LaTeX math output. License caveat resolved by treating PolyTool RIS as personal/research tooling under the modified Open Rail-M license; revisited if commercialization changes the posture. Fallback to pdfplumber for environments without GPU or where Marker fails.

2. **RAG control flow — PaperQA2's algorithm, wired to our stack.** Copy the agentic loop, citation traversal, contextual summarization (RCS), and source-handle mapping. Replace the OpenAI/LiteLLM defaults with our ChromaDB + SQLite FTS5 + Gemini Flash evaluation gate.

3. **Pre-fetch filter — Semantic Scholar API + S2FOS + SPECTER2 + SVM topic classifier.** Used to decide whether a paper is on-topic before downloading. S2FOS gives field-of-study labels; SPECTER2 gives scientific-document embeddings; an arXiv-Sanity-Lite-style SVM trained on operator-curated positive/negative examples sets the on-topic threshold. The expensive LLM evaluation gate runs only on papers that pass this filter.

4. **Multi-source harvesters — Semantic Scholar API as primary metadata source, plus targeted scrapers for SSRN, NBER, OpenReview.** Semantic Scholar covers the broad metadata + PDF-URL surface across publishers and preprint servers. SSRN/NBER/OpenReview scrapers fill domain-specific gaps that Semantic Scholar misses, with explicit session/cookie/redirect handling per the survey's "what we should not do" list.

5. **Evaluation harness — SciQAG/SciDQA-style benchmark for measuring our system.** Adopt their evaluation protocol (QA pairs tied to specific paper sections/figures/equations). Build a domain-specific golden set covering market microstructure / prediction markets / quantitative finance.

### Defer

6. **Late chunking (Jina AI).** Adopt only after Marker is producing structured Markdown/JSON and we have a baseline retrieval benchmark to compare against. Premature without that baseline.

7. **RAPTOR hierarchical retrieval.** Defer until we have evidence the flat retrieval is the bottleneck. Adopt if benchmarks show queries needing high-level synthesis are failing.

8. **Dolma (PaperMage replacement).** Watch for stability and adoption. PaperMage itself is unstable; Dolma may be the right entity-layer abstraction once mature.

### Skip

9. **Nougat as primary parser.** Non-commercial license blocks RIS use; autoregressive decoding too slow for batch ingestion at the scale we need.

10. **GROBID as the primary parser for math-heavy PDFs.** Math handling is too unreliable per the survey. Reconsider only for structural metadata (header, references) as a complement to Marker, not a replacement.

11. **PaperQA2's full default stack.** Copy the algorithm and citation logic; do not adopt their OpenAI-centric vector DB and embedding defaults. They undermine our goal of a controllable local RIS.

12. **ColBERTv2 / PLAID late-interaction retrieval.** Infrastructure cost unjustified at our current scale. SPECTER2 single-vector embeddings perform well enough on scientific documents per the survey's evidence. Reconsider only if benchmarks show single-vector retrieval is the dominant bottleneck.

13. **PyMuPDF4LLM as primary parser.** AGPL-3.0 license problematic. Commercial PyMuPDF Pro license is an additional cost we don't need given Marker covers the same use cases under more permissive terms.

14. **Unstructured as primary parser for math-heavy papers.** No LaTeX math handling. Acceptable as a fallback for non-math content (general blogs, news), not for academic.

15. **arXiv-Sanity-Lite as a runnable component.** Pattern is good (TF-IDF + SPECTER + SVM); the code is unmaintained and arXiv-only. Reimplement the pattern with SPECTER2 in our own pre-filter layer.

16. **SciQAG/SciDQA as RAG systems.** They are benchmarks, not pipelines. Use for evaluation only.

## Alternatives Considered

- **Build everything from scratch on top of the current pdfplumber fix.** Rejected — the survey shows mature open-source primitives exist for every layer. Reinventing them costs months for marginal control gains.
- **Adopt PaperQA2 wholesale, including its vector DB.** Rejected — the OpenAI-centric default stack contradicts our LLM Policy (Tier 1 free providers, Gemini primary). Surgically extracting the algorithm preserves the value while keeping our infrastructure.
- **Skip Marker and stay with pdfplumber permanently.** Rejected — pdfplumber handles text but not tables/math/structure. The five gaps identified in the survey (especially math-aware retrieval and source-handle precision) remain unmet.
- **Adopt GROBID as the primary parser.** Rejected per survey evidence on math handling. Considered for structural metadata fallback only.
- **Use Semantic Scholar without an SVM topic classifier.** Rejected — S2FOS field-of-study labels are coarse (e.g., "Economics" vs. "Computer Science"); a domain-specific SVM trained on operator-curated examples is needed to filter at the granularity of "market microstructure" or "prediction-market microeconomics."

## Why This Order

The four-layer architecture is built bottom-up because each layer depends on the previous:

1. PDF download (pdfplumber) — already specced as immediate-fix work packet
2. Parser upgrade (Marker) — depends on (1) for fallback path
3. RAG control flow (PaperQA2 patterns) — depends on (2) producing structured input worth running RAG over
4. Pre-fetch filter — depends on volume from (4) being high enough to need filtering. Multi-source harvesters depend on (3) — without good filtering, multi-source ingestion floods the evaluation gate

Skipping the order produces wasted work. Building Marker integration before fixing PDF download means working around a half-broken foundation. Building multi-source harvesters before pre-fetch filtering means burning Gemini quota on irrelevant papers.

## Impact

- The current immediate-fix work packet ([[Work-Packet - Academic Pipeline PDF Download Fix]]) ships unchanged. It is now correctly understood as the *first layer* of the four-layer target, not a one-off bug fix.
- Five new work packets land in `12-Ideas/` as stubs: Marker integration, PaperQA2 RAG control flow, pre-fetch SVM filter, multi-source harvesters, evaluation benchmark. Each gets a date and scope when activated.
- The five guardrails from the survey's "what we should not do" list are durable — every future RIS packet (academic or otherwise) checks against them before adopting any project.
- Other ingestion pipelines (reddit, blog, github, youtube) are out of scope for this decision. They have their own scope, and the survey was specifically about scientific RAG. Each will need its own diagnosis if/when it surfaces issues.

## Cross-references

- [[11-Scientific-RAG-Pipeline-Survey]] — full survey output (source-of-truth for findings)
- [[11-Scientific-RAG-Target-Architecture]] — the four-layer design
- [[2026-04-27 Academic Pipeline Diagnosis]] — bug that triggered the survey
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — immediate fix (layer 1)
- [[RIS]] — module
- [[RAG]] — module
- [[Phase-2-Discovery-Engine]] — parent phase
- [[Decision - RIS Evaluation Scoring Policy]] — eval gate scoring (still authoritative for layer 1's evaluator)
- [[Decision - RIS n8n Pilot Scope]] — n8n alerting surface (still authoritative)
- [[LLM-Policy]] — Tier 1 provider posture (constrains layer 3 choices)
