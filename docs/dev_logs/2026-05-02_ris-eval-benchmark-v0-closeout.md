# RIS Eval Benchmark v0 — Close-out

**Date:** 2026-05-02  
**Work packet:** L5 Scientific RAG Evaluation Benchmark v0 — post-baseline close-out  
**Author:** operator + Claude Code  

---

## Summary

Baseline v0 was created and all associated documentation was finalized. The bulk-accept
shortcut used for the initial QA review is explicitly marked as a one-time expedient in
the runbook, not a durable workflow. Next recommended work is pre-fetch relevance
filtering to drive off_topic_rate below 10%.

---

## Baseline Metrics

| Metric | Value | Rule fired? |
|--------|-------|-------------|
| Off-topic rate | 30.43% (7/23) | **Rule A** — primary recommendation |
| Fallback rate | 0.0% (0/23) | No |
| Retrieval P@5 | 1.0 (35/35 papers found) | No |
| Answer correctness | 11.43% (4/35 substrings in retrieved chunk) | No |
| Citation traceability | 11.43% (4/35 fully traceable) | No |
| Median chunk count | 25 | No |
| Suspicious low-chunk records | 3 (no body text) | No |
| Duplicate/dedup | 0 hash dupes, 1 title dupe | No |
| Parser quality (equation_heavy) | 100% not parseable | **Rule D** — secondary/heuristic |
| **Recommendation** | **A — Pre-fetch Relevance Filtering** | |

Baseline artifact: `artifacts/research/eval_benchmark/baseline_v0.json`  
Benchmark report: `artifacts/research/eval_benchmark/2026-05-02_benchmark_report.md`

---

## Files Updated

| File | Change |
|------|--------|
| `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md` | **Created** — full feature doc with metrics, interpretation, limitations, next steps |
| `docs/runbooks/research_eval_benchmark.md` | **Updated** — Step 2 current-state note, explicit anti-bulk-accept warning; Step 5 current-state note with locked baseline metrics |
| `docs/INDEX.md` | **Updated** — feature doc row in Features table; two new dev log rows in Recent Dev Logs |
| `docs/CURRENT_DEVELOPMENT.md` | **Updated** — L5 eval benchmark added to Recently Completed; Pre-fetch Relevance Filtering documented as next RIS packet in Notes for the Architect |
| `docs/dev_logs/2026-05-02_ris-eval-benchmark-golden-qa-finalized.md` | Prior session — 35-pair QA finalization and dry-run |
| `docs/dev_logs/2026-05-02_ris-eval-benchmark-v0-closeout.md` | **This file** |

---

## Bulk-Accept Cleanup

The bulk-accept shortcut used to review the 35 QA pairs was applied as a one-time
expedient for establishing the initial baseline. It is **not** encoded as a durable
workflow.

**Where bulk-accept language was removed or qualified:**

1. **`docs/runbooks/research_eval_benchmark.md` Step 2** — Added explicit warning:
   > "Operator review of each pair is required. Do not bulk-accept QA candidates without
   > individually verifying that the expected_answer_substring answers the question and is
   > present verbatim in the paper body. The v0 baseline was established via a one-time
   > expedited review pass (bulk-accept + 4 targeted fixes); future QA additions must be
   > reviewed individually."

2. **`docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md`** — Added callout block:
   > "This one-time review used a bulk-accept pass... This was appropriate for establishing
   > the initial baseline, not a template for future QA set reviews."

3. **`tests/fixtures/research_eval_benchmark/golden_qa_v0.json`** — The `description`
   field and `verification_source` fields contain no bulk-accept language. No change needed.

4. **`artifacts/research/eval_benchmark/QA_OPERATOR_REVIEW_v0.md`** — This is a
   historical artifact of the review session, not a durable instruction doc. Retaining
   as-is; it accurately records the review table with no erroneous prescriptions.

**Grep check:** `grep -r "bulk.accept\|accept by default\|default accept" docs/` now
returns only the runbook (which states it as a one-time exception) and feature doc
(same context) and this dev log. No durable "always bulk-accept" instruction exists.

---

## Interpretation Notes

### Why P@5 = 1.0 but answer_correctness = 11.43%

BM25 reliably routes to the correct paper (35/35 papers found at rank ≤5). However,
the answer substring is searched against the chunk text window returned — not the full
paper body. Only 4/35 answer substrings appear within the ranked chunk boundaries.
This is a chunking/ranking limitation, not an indexing failure. The scoped lexical
index is working correctly.

### Why Rule D is secondary and not actionable now

Rule D fires because pdfplumber plain-text extraction cannot produce structured equation
detection. 100% "not parseable" for equation_heavy papers is the expected baseline for
pdfplumber — it is not a regression or failure. Marker is already available as an
optional Layer 1 experimental parser. Recommending Marker production rollout based
solely on Rule D would be premature and misreads the heuristic. Rule A (off-topic rate)
is the correct priority.

### The 7 off-topic papers

Three were intentional outliers added to validate the off-topic detector. The other four
crept in from early broad-topic ingestion passes. All seven are candidates for removal or
reclassification once pre-fetch relevance filtering is implemented. The three
clearly-unrelated papers (Hastelloy-X materials science, head/neck cancer ML,
e-commerce conversion modeling) should be removed first.

---

## Next Recommended Packet

**Pre-fetch Relevance Filtering / Corpus Quality Improvement**

Goal: filter papers at the point of `research-acquire` ingestion using a seed-topic
relevance scorer so off-topic papers do not enter the KnowledgeStore corpus.

Trigger: off_topic_rate = 30.43% — Rule A fires and takes priority over all other
recommendations.

Target after implementation: off_topic_rate < 10%, Rule A no longer fires.

Scope (not starting — documenting for next session):
- Add relevance pre-filter to `research-acquire` pipeline
- Score candidate papers against PolyTool seed topics before insertion
- Tag or reject papers scoring below relevance threshold
- Re-run benchmark and compare to baseline_v0

---

## Remaining Limitations After Close-out

1. **3 no-body stub papers** in corpus (chunk_count=1, body_source=unknown):
   - `0838c7de...` — HF microstructure noise (duplicate entry of `0c8b3c3a...`)
   - `bad51e5d...` — Homogenous Properties of Automated Market Makers
   - `d744370b...` — Prediction Market Microstructure and Informed Trading
   Remedy: `research-acquire --url <url>` re-ingest pass; not urgent.

2. **Citation traceability at 11.43%** — All 35 QA pairs lack page numbers and 31 lack
   stored passage quotes. Adding page annotations and passage quotes to QA pairs would
   materially improve metric 7 without touching the retrieval pipeline.

3. **1 title duplicate** — Two records with the same title in the corpus (HF microstructure
   noise). One is the stub entry (0838c7de..., no body); the other is the full record
   (0c8b3c3a..., pdf body). The stub should be removed or merged in a corpus maintenance
   pass.

4. **answer_correctness_rate = 11.43%** — Chunk-boundary mismatch: the BM25 top-ranked
   chunk doesn't always contain the exact answer substring. This improves with better
   chunking parameters or semantic re-ranking (Layer 4 work, not yet started).

---

## Codex Review

Tier: Skip — docs-only close-out; no execution-path code changed.
