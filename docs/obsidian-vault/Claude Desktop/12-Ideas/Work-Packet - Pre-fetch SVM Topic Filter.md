---
tags: [work-packet, ris, ingestion, filtering, stub]
date: 2026-04-27
status: stub
priority: medium
phase: 2
target-layer: 3
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0)"
  - "Operator review queue accumulating accept/reject decisions (~30+ each)"
---

# Work Packet (stub) — Pre-fetch SVM Topic Filter

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate when (a) the operator has accumulated ~30+ accept and ~30+ reject decisions in the YELLOW review queue providing labeled training data, OR (b) Layer 4 multi-source harvesting is approaching activation and quota burn becomes a concern.

## Layer

Layer 3 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

A pre-fetch decision step that runs before the LLM evaluation gate. Inputs: paper metadata (title + abstract + fields-of-study). Outputs: on-topic decision with confidence score. Implementation:

1. SPECTER2 embedding of (title + abstract)
2. S2FOS field-of-study labels
3. Domain-specific SVM trained on operator accept/reject decisions plus a seed set
4. Above threshold → proceed to fetch + parse + LLM gate. Below threshold → skip with logged reason.

Training data accumulates from operator decisions in the YELLOW queue. SVM retrains nightly. Cold-start uses 20-50 hand-picked positive examples (Avellaneda-Stoikov, Kelly, Jon-Becker, seeded foundational papers) and 20-50 hand-picked off-topic negatives.

## Scope guards

- Do NOT replace the LLM evaluation gate — this is upstream of it, not a substitute
- SVM only — no neural classifier in this packet (per arXiv-Sanity-Lite pattern; minimal infra)
- Threshold tunable via config; start permissive, tighten as operator review accumulates
- Logged decisions feed back into training data via the acquisition review JSONL

## Acceptance gates (to be detailed when activated)

1. SVM achieves >80% precision on a held-out test set drawn from operator decisions
2. False-negative rate <10% on the seed positive set (we don't accidentally filter out core papers)
3. Filter throughput >100 papers/sec (the cheap step before the expensive ones)
4. Daily retraining script runs cleanly, ledger of model versions preserved

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[11-Scientific-RAG-Pipeline-Survey]] — arXiv-Sanity-Lite, Semantic Scholar API, S2FOS, SPECTER2 entries have the full evaluation
- [[Decision - RIS Evaluation Scoring Policy]] — scoring policy this filter feeds into
