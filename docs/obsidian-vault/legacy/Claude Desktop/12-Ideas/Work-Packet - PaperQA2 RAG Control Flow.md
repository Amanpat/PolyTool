---
tags: [work-packet, ris, retrieval, rag, complete]
date: 2026-04-29
status: complete
completed: 2026-05-09
priority: medium
phase: 2
target-layer: 2
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped)"
  - "[[Work-Packet - Marker Structural Parser Integration]] (Layer 1 — production rollout)"
  - "[[Work-Packet - Scientific RAG Evaluation Benchmark]] (Layer 5 — provides baseline metrics to measure improvement against)"
---

# Work Packet — PaperQA2 RAG Control Flow

> [!INFO] Completion status
> Closed as bounded L2 v1 on 2026-05-09. Shipped `research-query`: multi-angle
> KnowledgeStore query, paper-level grouping, citation metadata, graceful fallback,
> and a query-time Marker-ready guard (`body_source=marker`, `body_length>=5000`).
> Full ChromaDB retrieval, RCS/LLM synthesis, and page-level citations are deferred
> to future L2.x work.
>
> **Operator-tested v1 (2026-05-09):** `research-query` validated end-to-end over a
> 3-paper Marker-indexed corpus (79 chunks, 373 claims). Both test queries returned
> `had_fallback=false` with `body_source=marker` citations. Windows/local warm-thread
> path. Docker/GPU IPC batch performance validation is optional follow-up only.

## Layer

Layer 2 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What shipped

Adopted the PaperQA2-inspired paper-level search pattern without importing
PaperQA2's vector DB, embedding defaults, or LiteLLM stack.

A new `polytool research-query` command takes a question and returns structured
paper-level citations from the KnowledgeStore academic corpus. It is additive;
the existing `rag-query` command is unchanged.

The shipped L2 v1 path is KS-only because ChromaDB chunk metadata does not yet
store `body_source`. New academic ingestion is gated by Marker readiness, and the
query path re-checks source metadata so legacy pdfplumber or short-body rows are
not returned.

## Scope guards

- Copy the paper-level search/control-flow pattern from PaperQA2 (Apache-2.0 — attribute in file header)
- Do NOT pull in PaperQA2's vector DB, embedding defaults, or LiteLLM dependency
- Keep the existing `rag-query` command working — `research-query` is additive
- Embeddings/ChromaDB and LLM synthesis are deferred in L2 v1
- Do NOT change the corpus ingestion path — this packet only changes retrieval

## Reference Materials

Primary references used to scope L2 v1 and future L2.x work:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — the PaperQA2 entry has the full evaluation including the algorithm description, citation-to-page mapping logic, and what to copy vs. what to avoid (their OpenAI defaults). Primary reference.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 2 in "Adopt" specifies the PaperQA2 algorithm, with the explicit warning to NOT adopt their default stack wholesale. Constrains scope.
3. **PaperQA2 source code** — `https://github.com/future-house/paper-qa`, Apache-2.0. Specifically the agentic loop in `paperqa/agents/`, the contextual summarization in `paperqa/contexts/`, and the citation traversal in `paperqa/llms/`. Not all needed; pick the patterns that map to our stack.
4. **`[[Work-Packet - Scientific RAG Evaluation Benchmark]]`** (when shipped) — provides the P@5 / answer-quality baseline this packet measures improvement against.
5. **L1 Marker output schema** — once Layer 1 ships, the architect should inspect what `body_text` actually looks like for a Marker-parsed paper (LaTeX, sections, tables) so retrieval is designed around real input, not assumed input.

## Acceptance gates (L2 v1)

1. Functional query path exists — `python -m polytool research-query --question "..."`
2. Retrieval is restricted to Marker/RAG-ready academic docs — query-time guard checks `body_source=marker` and `body_length>=5000`
3. Bad legacy docs are rejected — pdfplumber, missing metadata, and short Marker rows are not cited
4. CLI/operator path is documented in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
5. Tests cover happy path, bad docs, fallback, grouping, deduplication, and CLI validation — `tests/test_research_query.py` has 36 passing tests

## Deferred L2.x Work

- ChromaDB academic retrieval once `body_source` is indexed in chunk metadata
- Full Recursive Contextual Summarization (RCS)
- Page-level citations
- LLM answer synthesis through the provider layer

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[Work-Packet - Marker Structural Parser Integration]] — provides structured input
- [[Work-Packet - Scientific RAG Evaluation Benchmark]] — provides baseline + measurement
- [[11-Scientific-RAG-Pipeline-Survey]] — PaperQA2 entry
- [[RAG]] — module being extended
