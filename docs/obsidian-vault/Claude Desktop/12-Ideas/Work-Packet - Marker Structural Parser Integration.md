---
tags: [work-packet, ris, ingestion, academic, stub]
date: 2026-04-27
status: stub
priority: medium
phase: 2
target-layer: 1
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0)"
---

# Work Packet (stub) — Marker Structural Parser Integration

> [!INFO] Stub status
> This packet is a placeholder so the architecture cross-links resolve. Activate (status → ready) only after Layer 0 has shipped and we have a baseline to compare Marker's output against.

## Layer

Layer 1 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

Replace pdfplumber's flat text extraction with Marker's structured Markdown/JSON output in the academic pipeline. Marker preserves sections, tables, equations (as LaTeX), and images. Output goes into the same `body_text` field, with structural markers downstream layers can use.

pdfplumber stays as fallback for CPU-only environments, large PDFs exceeding Marker's memory budget, or documents Marker fails on. The `body_source` metadata field grows to include `marker`, `marker_llm_boost`, `pdfplumber_fallback`.

## Scope guards

- Replace pdfplumber as default; do not remove it
- Marker's optional `--use_llm` mode disabled by default in the packet (extra cost, latency)
- License posture: research/personal tooling under modified Open Rail-M; revisit if commercialization changes posture
- Do not change the chunker, the embedder, or the retrieval API in this packet — those are Layer 2

## Acceptance gates (to be detailed when activated)

1. Marker successfully parses 90%+ of a 50-paper test corpus (mix of arXiv, SSRN, NBER PDFs)
2. Output Markdown contains LaTeX math for equations in test set
3. Section headers preserved
4. Performance: <30s per typical paper on dev hardware (i7-8700K + 2070 Super)
5. Fallback path triggers on timeout or memory exceeded
6. Existing Layer 0 acceptance criteria still pass with Marker swapped in

## Open questions for activation

- GPU vs. CPU mode for production: `polytool-ris-scheduler` runs on partner machine — what hardware does it have?
- LLM-boost mode worth the latency? Decide after a sample run on the seed corpus.
- Storage: Marker output is significantly larger than pdfplumber text — does that change retention policy?

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — prerequisite (Layer 0)
- [[11-Scientific-RAG-Pipeline-Survey]] — Marker entry has the full evaluation
