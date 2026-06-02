---
title: "Work Packet — PaperQA2 RAG Control Flow"
type: work_packet
status: complete
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: reviewed
tags: [work-packet, ris, retrieval, rag, complete]
target_agent: claude-code
acceptance_criteria:
  - See body for full criteria
---

# Work Packet — PaperQA2 RAG Control Flow

> [!INFO] Completion status
> Closed as bounded L2 v1 on 2026-05-09. Shipped `research-query`: multi-angle
> KnowledgeStore query, paper-level grouping, citation metadata, graceful fallback,
> and a query-time Marker-ready guard (`body_source=marker`, `body_length>=5000`).
> RCS/LLM synthesis and page-level citations remain deferred to future L2.x work.
>
> **L2.1 ChromaDB semantic retrieval — COMPLETE 2026-05-25.** `_embed_body_into_chroma()`,
> `--reindex-chroma` CLI flag, and `check-chroma-links` subcommand shipped. ChromaDB vector
> search is now the primary retrieval path; KS lexical is the fallback. 3-paper category
> sample PASS. At Batch B closeout: 917 chunks / 21 papers / 0 orphans.
>
> **Academic RIS Developer/Operator Demo-Ready v1 FORMALLY CLOSED 2026-05-28.**
> Batch B (10 medium papers): done=20, failed=0, 7 semantic probes PASS.
> Codex final review: PASS. Feature doc: `docs/features/FEATURE-ris-academic-demo-ready-v1.md`.
> **NOT production-ready.** Batch C/D deferred to post-v1 hardening (Tier-3 approval required).
> Next work: Docker `jit-cache-check` only.
>
> **Operator-tested v1 (2026-05-09):** `research-query` validated end-to-end over a
> 3-paper Marker-indexed corpus (79 chunks, 373 claims). Both test queries returned
> `had_fallback=false` with `body_source=marker` citations. Windows/local warm-thread
> path. Docker/GPU IPC batch performance validation is optional follow-up only.

## Layer

Layer 2 of the [[Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What shipped

Adopted the PaperQA2-inspired paper-level search pattern without importing
PaperQA2's vector DB, embedding defaults, or LiteLLM stack.

A new `polytool research-query` command takes a question and returns structured
paper-level citations from the KnowledgeStore academic corpus. It is additive;
the existing `rag-query` command is unchanged.

The shipped L2 v1 path was KS-only because ChromaDB chunk metadata did not yet
store `body_source`. **L2.1 (2026-05-25) resolved this:** `_embed_body_into_chroma()`
now stores `body_source` in chunk metadata; ChromaDB semantic vector search is the
primary retrieval path. New academic ingestion is gated by Marker readiness, and the
query path re-checks source metadata so legacy pdfplumber or short-body rows are
not returned.

## Scope guards

- Copy the paper-level search/control-flow pattern from PaperQA2 (Apache-2.0 — attribute in file header)
- Do NOT pull in PaperQA2's vector DB, embedding defaults, or LiteLLM dependency
- Keep the existing `rag-query` command working — `research-query` is additive
- ~~Embeddings/ChromaDB deferred in L2 v1~~ — **ChromaDB semantic retrieval COMPLETE (L2.1, 2026-05-25)**; LLM synthesis still deferred
- Do NOT change the corpus ingestion path — this packet only changes retrieval

## Reference Materials

Primary references used to scope L2 v1 and future L2.x work:

1. **`[[legacy/Claude Desktop/08-Research/11-Scientific-RAG-Pipeline-Survey]]`** — the PaperQA2 entry has the full evaluation including the algorithm description, citation-to-page mapping logic, and what to copy vs. what to avoid (their OpenAI defaults). Primary reference.
2. **`[[legacy/Claude Desktop/09-Decisions/Decision - Scientific RAG Architecture Adoption]]`** — item 2 in "Adopt" specifies the PaperQA2 algorithm, with the explicit warning to NOT adopt their default stack wholesale. Constrains scope.
3. **PaperQA2 source code** — `https://github.com/future-house/paper-qa`, Apache-2.0. Specifically the agentic loop in `paperqa/agents/`, the contextual summarization in `paperqa/contexts/`, and the citation traversal in `paperqa/llms/`. Not all needed; pick the patterns that map to our stack.
4. **`[[claude-memory/work-packets/work-packet-scientific-rag-evaluation-benchmark]]`** (when shipped) — provides the P@5 / answer-quality baseline this packet measures improvement against.
5. **L1 Marker output schema** — once Layer 1 ships, the architect should inspect what `body_text` actually looks like for a Marker-parsed paper (LaTeX, sections, tables) so retrieval is designed around real input, not assumed input.

## Acceptance gates (L2 v1)

1. Functional query path exists — `python -m polytool research-query --question "..."`
2. Retrieval is restricted to Marker/RAG-ready academic docs — query-time guard checks `body_source=marker` and `body_length>=5000`
3. Bad legacy docs are rejected — pdfplumber, missing metadata, and short Marker rows are not cited
4. CLI/operator path is documented in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
5. Tests cover happy path, bad docs, fallback, grouping, deduplication, and CLI validation — `tests/test_research_query.py` has 36 passing tests

## Deferred L2.x Work

- ~~ChromaDB academic retrieval once `body_source` is indexed in chunk metadata~~ — **COMPLETE (L2.1, 2026-05-25)**
- Full Recursive Contextual Summarization (RCS) — still deferred
- Page-level citations — still deferred
- LLM answer synthesis through the provider layer — still deferred

## Cross-references

- [[legacy/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture]] — parent design
- [[Claude Desktop/09-Decisions/Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[claude-memory/work-packets/work-packet-marker-structural-parser-integration]] — provides structured input
- [[Claude Desktop/12-Ideas/Work-Packet - Scientific RAG Evaluation Benchmark]] — provides baseline + measurement
- [[Claude Desktop/08-Research/11-Scientific-RAG-Pipeline-Survey]] — PaperQA2 entry
- [[legacy/PolyTool/02-Modules/RAG]] — module being extended
