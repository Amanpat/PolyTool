---
tags: [work-packet, ris, retrieval, rag, stub]
date: 2026-04-29
status: stub
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

# Work Packet (stub) — PaperQA2 RAG Control Flow

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate after Layer 1 (Marker production) ships AND Layer 5 (Evaluation Benchmark) produces a baseline. The Layer 5 baseline is what tells us whether L2's added complexity actually improves retrieval — without it, L2 becomes guesswork.

## Layer

Layer 2 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

Adopt PaperQA2's agentic RAG control flow — paper-level search, chunk re-ranking, Recursive Contextual Summarization (RCS), citation traversal — and wire it to our existing ChromaDB + SQLite FTS5 + Gemini Flash stack. Replace PaperQA2's OpenAI/LiteLLM defaults with our provider layer.

A new `polytool research-query` command takes a question and returns answers with citations to specific PDF pages, replacing the current naïve `rag-query` for the academic family.

The Marker-structured input from Layer 1 (LaTeX equations, table structure, section headers, page numbers) is consumed natively — citations map to specific PDF pages because Marker preserves page metadata, and section-aware chunking becomes possible because section boundaries are explicit.

## Scope guards

- Copy the algorithm and citation logic from PaperQA2 (Apache-2.0 — attribute in file header)
- Do NOT pull in PaperQA2's vector DB, embedding defaults, or LiteLLM dependency
- Keep the existing `rag-query` command working — `research-query` is additive
- Embeddings stay SentenceTransformers (Tier 1 free)
- LLM steps route through existing provider layer (Gemini Flash primary, Ollama fallback)
- Do NOT change the corpus ingestion path — this packet only changes retrieval

## Reference materials for architect

The architect should read these before refining this stub into a full packet:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — the PaperQA2 entry has the full evaluation including the algorithm description, citation-to-page mapping logic, and what to copy vs. what to avoid (their OpenAI defaults). Primary reference.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 2 in "Adopt" specifies the PaperQA2 algorithm, with the explicit warning to NOT adopt their default stack wholesale. Constrains scope.
3. **PaperQA2 source code** — `https://github.com/future-house/paper-qa`, Apache-2.0. Specifically the agentic loop in `paperqa/agents/`, the contextual summarization in `paperqa/contexts/`, and the citation traversal in `paperqa/llms/`. Not all needed; pick the patterns that map to our stack.
4. **`[[Work-Packet - Scientific RAG Evaluation Benchmark]]`** (when shipped) — provides the P@5 / answer-quality baseline this packet measures improvement against.
5. **L1 Marker output schema** — once Layer 1 ships, the architect should inspect what `body_text` actually looks like for a Marker-parsed paper (LaTeX, sections, tables) so retrieval is designed around real input, not assumed input.

## Acceptance gates (to be detailed when activated)

1. Citations in output map to specific PDF pages — verify on 10-question test set drawn from the L5 golden set
2. RCS produces summaries that contain the cited content
3. Re-ranking measurably improves retrieval precision over raw similarity (per the L5 benchmark — target: P@5 improves by ≥0.10 over the L1+L0 baseline)
4. End-to-end query latency <30s on dev hardware for typical questions
5. Falls back gracefully when only L0 (text-only) docs remain in the index from before the L1 cleanup task runs
6. Citation accuracy ≥90% — citations point to PDF pages that actually contain the cited content

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[Work-Packet - Marker Structural Parser Integration]] — provides structured input
- [[Work-Packet - Scientific RAG Evaluation Benchmark]] — provides baseline + measurement
- [[11-Scientific-RAG-Pipeline-Survey]] — PaperQA2 entry
- [[RAG]] — module being extended
