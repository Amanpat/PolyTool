---
tags: [prompt-archive]
date: 2026-04-09
model: GLM-5 Turbo
topic: RAG Retrieval Quality Testing
---
# RAG Retrieval Quality Testing — Research Results

## Key Findings
1. **Golden test set:** 30-40 query-answer pairs labeled with relevant chunk/doc IDs. Cover 5 cognitive paths: factual, conceptual, cross-document, paraphrase, negative-control. Label parent doc IDs (not chunk IDs) to survive re-chunking.
2. **Metrics:** Recall@5 (most important — miss = hallucination), Precision@5 (context window efficiency), MRR (first relevant rank — "lost in the middle" syndrome).
3. **A/B testing:** Direct vs HyDE vs Query Decomposition vs Combined. Keep vector DB constant, change only query strategy. For niche domains, Direct or Decomposition often beats HyDE (introduces out-of-domain vocab).
4. **Silent failure detection:** Queries where Recall@5=0 but average distance is low (high confidence, wrong results). Compute Silent Failure Rate separately.
5. **DIY over frameworks:** For sub-5K doc corpus, deterministic IR metrics script beats RAGAS/DeepEval (which require LLM judge calls). Runs in milliseconds, 100% reproducible.

## Applied To
- RIS Phase 2 Priority 3 (RAG testing)
- `scripts/rag_benchmark.py` design

## Source
Deep research prompt, discussed in [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
