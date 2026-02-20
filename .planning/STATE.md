# Project State

## Current Position
- **Milestone:** v1.0 — Core RAG Pipeline
- **Current Phase:** 5 (Reranking)
- **Status:** In Progress

Last activity: 2026-02-20 - Completed quick-009: Roadmap 5 wrap-up PDR and marked ROADMAP.md [COMPLETE]

## Recent Progress
- Quick-002: Resolution provider chain (OnChainCTF + Subgraph + cascade), 13 new tests, ROADMAP renumbered (217 tests passing)
- Quick-001: Cross-encoder reranking with hybrid+rerank eval mode (101 tests passing)
- Phase 4.3: Offline RAG eval harness implemented with 20 passing tests
- Phase 4.2: Index reconcile mode for stale chunk cleanup
- Phase 4.1: Hybrid retrieval with FTS5 + RRF

## Key Decisions
- Chroma for vector store, SQLite FTS5 for lexical
- RRF k=60 (standard paper value) for fusion
- SHA256-based deterministic IDs
- Privacy-scoped filtering at both vector and lexical layers
- Cross-encoder reranking: opt-in, top_n=50 default, model cache via SENTENCE_TRANSFORMERS_HOME
- Default rerank model: cross-encoder/ms-marco-MiniLM-L-6-v2 (lightweight, proven)
- Resolution provider chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma (authoritative-first)
- No web3.py: raw JSON-RPC for on-chain reads (lighter dependency footprint)
- Resolution reason field for debugging/traceability
- Roadmap renumbering: Resolution Coverage as Roadmap 3 (data quality before analysis quality)
- Dual CLV variants: settlement sub-ladder (onchain_resolved_at only), pre-event sub-ladder (gamma closedTime/endDate/umaEndDate)
- Hypothesis ranking cascade: pre_event notional-weighted > settlement notional-weighted > combined > count-weighted fallback
- Roadmap 5 closed [COMPLETE]: CLV infra shipped but 0% coverage triggered kill condition; batch-run harness shipped fully; ROADMAP.md updated
- Mark 5.0 category [x] when code ships even if runtime coverage is 0% (upstream data gap, not code defect)

### Blockers/Concerns
None currently.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 001 | Offline reranking for hybrid retrieval (opt-in) | 2026-02-03 | 2bffaed | [001-offline-rerank-hybrid-retrieval](./quick/001-offline-rerank-hybrid-retrieval/) |
| 002 | Resolution provider chain (OnChainCTF + Subgraph) | 2026-02-10 | 81f17d7 | [002-resolution-provider-chain](./quick/002-resolution-provider-chain/) |
| 004 | hypothesis_candidates.json artifact + Hypothesis Candidates markdown section | 2026-02-20 | eaa39f2 | [4-build-hypothesis-candidates-json-artifac](./quick/4-build-hypothesis-candidates-json-artifac/) |
| 005 | Fix notional-weighted metrics null by normalizing position_notional_usd in scan.py | 2026-02-20 | b592d94 | [5-fix-notional-weighted-metrics-null-by-no](./quick/5-fix-notional-weighted-metrics-null-by-no/) |
| 006 | Dual CLV variants (clv_settlement + clv_pre_event) with hypothesis ranking preference | 2026-02-20 | 0407007 | [6-add-dual-clv-variants-clv-settlement-anc](./quick/6-add-dual-clv-variants-clv-settlement-anc/) |
| 009 | Roadmap 5 wrap-up PDR + mark ROADMAP.md [COMPLETE] | 2026-02-20 | 4e84a36 | [9-roadmap-5-wrap-up-pdr-and-mark-complete-](./quick/9-roadmap-5-wrap-up-pdr-and-mark-complete-/) |
