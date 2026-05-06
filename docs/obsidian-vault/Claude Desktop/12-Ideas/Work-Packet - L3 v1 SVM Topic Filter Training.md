---
tags: [work-packet, ris, filtering, svm, stub]
date: 2026-05-05
status: stub
priority: high
phase: 2
target-layer: 3 (v1)
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Prefetch Label Discovery Mode]] (L3.2 — shipped 2026-05-05)"
  - "SVM trigger met: ≥30 allow + ≥30 reject labels in `artifacts/research/svm_filter_labels/labels.jsonl`"
trigger-condition: "≥30 allow + ≥30 reject labels — MET 2026-05-05 (30 allow / 31 reject)"
---

# Work Packet (stub) — L3 v1 SVM Topic Filter Readiness + Training

> [!NOTE] Stub — ready to activate
> Trigger condition met 2026-05-05 (30 allow / 31 reject).
> This packet is ready to be promoted to Active as Feature 3.
> Director must explicitly open this packet before implementation begins.

---

## Goal

Train and integrate an L3 v1 SVM-based topic filter that replaces (or supplements)
the lexical `RelevanceScorer` in the prefetch pipeline. The trained model generalizes
beyond keyword overlap using learned embeddings.

---

## Trigger

SVM training is triggered when the label store reaches **≥30 allow AND ≥30 reject**
labels in `artifacts/research/svm_filter_labels/labels.jsonl`.

**Status: MET** — 30 allow / 31 reject as of 2026-05-05.

---

## Scope (to be refined at activation)

1. **Embeddings**: SPECTER2 (paper-optimized sentence embeddings) and/or S2FOS
   (field-of-study classifier features) from Semantic Scholar.
2. **Classifier**: Scikit-learn SVM (`sklearn.svm.SVC` or `LinearSVC`) trained
   on labeled examples from `labels.jsonl`.
3. **Integration**: Wire trained model into `RelevanceScorer` or create a parallel
   `SVMRelevanceScorer` that the prefetch pipeline can dispatch to.
4. **Evaluation**: Measure precision/recall on held-out labels; compare to lexical
   v1.1 baseline (Scenario B 5.88% off-topic rate).
5. **CLI surface**: `research-prefetch-filter-train` or equivalent command for
   model training, evaluation, and export.

---

## Non-Goals (stub — may change at activation)

- No production deployment until evaluation passes.
- No L2 (PaperQA2) activation.
- No L4 harvesters.
- No changes to the label store format or `ReviewQueueStore`.

---

## Deferred Dependency

**Marker Docker/Linux IPC Warm-Worker (Option A)** must be revisited after this
L3/SVM stream completes or before L2 production launch (whichever comes first).
Do not let this slip past SVM closeout.

---

## Cross-References

- [[Work-Packet - Prefetch Label Discovery Mode]] — L3.2 (completed; label source)
- [[11-Scientific-RAG-Target-Architecture]] — parent design
- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — canonical L3/L3.1 feature doc
- `artifacts/research/svm_filter_labels/labels.jsonl` — label store (30 allow / 31 reject)
- `packages/research/relevance_filter/scorer.py` — current lexical scorer to be extended/replaced
- `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-closeout.md` — closeout that triggered this packet
