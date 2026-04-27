---
tags: [work-packet, ris, retrieval, rag, stub]
date: 2026-04-27
status: stub
priority: medium
phase: 2
target-layer: 2
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0)"
  - "[[Work-Packet - Marker Structural Parser Integration]] (Layer 1)"
---

# Work Packet (stub) — PaperQA2 RAG Control Flow

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate only after Layer 1 (Marker) has shipped and is producing structured output.

## Layer

Layer 2 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

Adopt PaperQA2's agentic RAG control flow — paper-level search, chunk re-ranking, Recursive Contextual Summarization (RCS), citation traversal — and wire it to our existing ChromaDB + SQLite FTS5 + Gemini Flash stack. Replace PaperQA2's OpenAI/LiteLLM defaults with our provider layer.

A new `polytool research-query` command takes a question and returns answers with citations to specific PDF pages, replacing the current naïve `rag-query` for the academic family.

## Scope guards

- Copy the algorithm and citation logic from PaperQA2 (Apache-2.0 — attribute in file header)
- Do NOT pull in PaperQA2's vector DB, embedding defaults, or LiteLLM dependency
- Keep the existing `rag-query` command working — `research-query` is additive
- Embeddings stay SentenceTransformers (Tier 1 free)
- LLM steps route through existing provider layer (Gemini Flash primary, Ollama fallback)

## Acceptance gates (to be detailed when activated)

1. Citations in output map to specific PDF pages — verify on 10-question test set
2. RCS produces summaries that contain the cited content
3. Re-ranking measurably improves retrieval precision over raw similarity (per the Layer-5 benchmark)
4. End-to-end query latency <30s on dev hardware for typical questions
5. Falls back gracefully when only Layer 0 (text-only) docs are in the index

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[11-Scientific-RAG-Pipeline-Survey]] — PaperQA2 entry has the full evaluation
- [[RAG]] — module being extended
