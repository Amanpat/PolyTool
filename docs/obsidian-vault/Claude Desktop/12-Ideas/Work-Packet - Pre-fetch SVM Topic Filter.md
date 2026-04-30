---
tags: [work-packet, ris, ingestion, filtering, stub]
date: 2026-04-29
status: stub
priority: medium
phase: 2
target-layer: 3
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped)"
  - "[[Work-Packet - Scientific RAG Evaluation Benchmark]] (Layer 5 — quantifies off-topic rate, justifies activation)"
  - "Operator review queue accumulating accept/reject decisions (~30+ each) OR Layer 5 measures off-topic rate >30%"
---

# Work Packet (stub) — Pre-fetch SVM Topic Filter

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate when **either** (a) the operator has accumulated ~30+ accept and ~30+ reject decisions in the YELLOW review queue providing labeled training data, **or** (b) Layer 5 measures off-topic rate >30% confirming a filter is needed, **or** (c) Layer 4 multi-source harvesting is approaching activation and quota burn becomes a concern. Layer 5 is the cleanest activation signal.

## Layer

Layer 3 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

A pre-fetch decision step that runs before the LLM evaluation gate. Inputs: paper metadata (title + abstract + fields-of-study). Outputs: on-topic decision with confidence score. Implementation:

1. SPECTER2 embedding of (title + abstract)
2. S2FOS field-of-study labels (when Semantic Scholar metadata is available)
3. Domain-specific SVM trained on operator accept/reject decisions plus a seed set
4. Above threshold → proceed to fetch + parse + LLM gate. Below threshold → skip with logged reason.

Training data accumulates from operator decisions in the YELLOW queue. SVM retrains nightly. Cold-start uses 20-50 hand-picked positive examples (Avellaneda-Stoikov, Kelly, Jon-Becker, seeded foundational papers) and 20-50 hand-picked off-topic negatives.

## Scope guards

- Do NOT replace the LLM evaluation gate — this is upstream of it, not a substitute. The LLM gate scores depth and substance; the SVM filters relevance.
- SVM only — no neural classifier in this packet (per arXiv-Sanity-Lite pattern; minimal infra)
- Threshold tunable via config; start permissive (low false-negative rate), tighten as operator review accumulates
- Logged decisions feed back into training data via the acquisition review JSONL
- Filter runs on metadata only — no PDF download required to make the decision
- Do NOT modify Layer 4 fetchers — they call the filter, the filter doesn't reach into them

## Reference materials for architect

The architect should read these before refining this stub:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — three entries are directly relevant:
   - **arXiv-Sanity-Lite** (Karpathy) — provides the TF-IDF + SPECTER + SVM pattern. The repo is unmaintained but the architecture is the reference. Survey notes specifically what to copy and what to modernize.
   - **Semantic Scholar API + S2FOS + SPECTER2** — provides field-of-study classification and scientific-document embeddings. S2FOS is a linear SVM over character n-gram TF-IDF; SPECTER2 is a neural embedding trained on citation graphs. Both are Apache-2.0 / MIT.
   - **OpenReview Finder** (danmackinlay) — working reference implementation showing SPECTER2 + ChromaDB integration. Survey calls it "easy to adapt." Code review this for the integration pattern.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 3 in "Adopt" specifies this exact combination (Semantic Scholar + S2FOS + SPECTER2 + arXiv-Sanity-style SVMs). The architect inherits this design choice; do not re-litigate it.
3. **`[[Decision - RIS Evaluation Scoring Policy]]`** — establishes how the LLM gate scores documents. The SVM filter is upstream of this; the two should not duplicate work.
4. **L5 baseline report** (when shipped) — provides the off-topic rate measurement that justifies this layer's complexity. Read it before tuning the SVM threshold.

## Acceptance gates (to be detailed when activated)

1. SVM achieves >80% precision on a held-out test set drawn from operator decisions
2. False-negative rate <10% on the seed positive set (we don't accidentally filter out core papers like Avellaneda-Stoikov or Kelly)
3. Filter throughput >100 papers/sec (the cheap step before the expensive ones)
4. Daily retraining script runs cleanly, ledger of model versions preserved in `artifacts/research/svm_filter_models/`
5. Off-topic rate measured by L5 drops by ≥50% with the filter active vs. without
6. Training data audit: every accept/reject decision from the YELLOW queue produces exactly one labeled example in the training set

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision (item 3)
- [[Work-Packet - Scientific RAG Evaluation Benchmark]] — quantifies the off-topic rate this filter addresses
- [[11-Scientific-RAG-Pipeline-Survey]] — arXiv-Sanity-Lite, Semantic Scholar API, S2FOS, SPECTER2, OpenReview Finder entries
- [[Decision - RIS Evaluation Scoring Policy]] — LLM gate scoring policy this filter feeds into
