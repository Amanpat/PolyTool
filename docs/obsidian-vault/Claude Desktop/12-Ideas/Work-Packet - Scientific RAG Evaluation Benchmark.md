---
tags: [work-packet, ris, evaluation, scientific-rag]
date: 2026-04-29
status: ready
priority: high
phase: 2
target-layer: 5
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped 2026-04-27)"
assignee: architect → Claude Code agent
---

# Work Packet — Scientific RAG Evaluation Benchmark v0

> [!IMPORTANT] Activation rationale
> This packet was promoted from stub to ready on 2026-04-29 because it is the natural next step after Layer 0 shipped. Without a benchmark, every subsequent layer (Marker production, PaperQA2 retrieval, SVM filter, multi-source) ships blind — there is no signal to know whether each change improved the system or made it worse. L5 is the **scoreboard** that turns the rest of the roadmap from sequential commitment into evidence-based decisions.

## Layer

Layer 5 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]]. Strictly speaking it sits adjacent to the four-layer ingest stack; it measures the stack rather than participating in it. The label "Layer 5" is convention for "the fifth packet in the scientific RAG roadmap," not a stage in the pipeline.

## Purpose

Measure the current Layer 0 + pdfplumber pipeline before committing to any further pipeline change. Provide a baseline of corpus quality and retrieval quality. Produce a single benchmark report that tells the operator and architect which change matters most.

The report's output is a recommendation among five candidates:

- **A) Pre-fetch relevance filtering (Layer 3)** — recommend if off-topic rate is high
- **B) Old-paper re-ingest cleanup** — recommend if Layer 0 fallback rate is high or chunk-count distribution is suspicious
- **C) PaperQA2-style retrieval (Layer 2)** — recommend if retrieval P@5 is the bottleneck
- **D) Marker production validation (Layer 1)** — recommend if parser-quality issues dominate (e.g., equations missing, tables mangled)
- **E) Chunking changes** — recommend if chunk distribution or low-chunk records suggest the chunker is the issue

L5 is not just a measurement — it is a **decision instrument**.

## What ships

A new CLI command `polytool research-eval-benchmark` and supporting infrastructure that produces a structured benchmark report covering nine metrics. The report is human-readable Markdown plus a machine-readable JSON for trend tracking.

### The nine metrics

The architect's recommendation specified nine metric categories. Each gets a concrete definition in this packet:

1. **Off-topic rate** — fraction of ingested papers whose stored content does not match any seeded research topic. Measurement: for each paper in the corpus, run the title and abstract through a lightweight relevance classifier (initial implementation: keyword overlap with a seed-topic list of 10-15 phrases like "prediction market", "market microstructure", "Avellaneda-Stoikov", "Kelly criterion", "optimal execution", "limit order book", "informed trading"). Below threshold = off-topic. Output: percentage off-topic, list of off-topic source_ids for review.

2. **Body-source distribution** — count and percentage of stored documents tagged `body_source=pdf`, `body_source=abstract_fallback`, `body_source=marker` (zero pre-Layer-1), and any other source values found. Output: pie-chart-equivalent table.

3. **Fallback rate** — fraction of academic ingests that fell back from PDF to abstract. Sub-categorized by `fallback_reason` (PDF download failed, extraction failed, body too short). Output: percentage and breakdown by reason.

4. **Chunk count distribution** — histogram of chunk counts per document. Highlights both ends: very low chunk counts (<3, suggesting short body or bad parse) and very high counts (>200, suggesting a book-length document or extraction noise). Output: histogram + summary stats (mean, median, p5, p95).

5. **Low-chunk suspicious records** — documents with chunk_count < 3 listed individually with title, body_length, body_source, and a "review priority" flag. These are the documents most likely to be silently broken. Output: ranked table.

6. **Retrieval answer quality on fixed questions** — run a curated golden QA set (see "Golden QA Set" below) against the current retrieval path. For each question, measure: was the correct passage retrieved in top-5? did the answer match the golden answer (LLM judge or exact-match heuristic)? Output: P@5, answer-correctness rate, per-question detail.

7. **Citation/source traceability** — for each retrieved chunk, can the report link back to the source PDF, the page number (if available), and the exact passage in the cached body? Measurement: for the golden QA set, attempt to reconstruct the citation. Output: percentage of citations successfully reconstructed.

8. **Duplicate/dedup behavior** — count documents that appear to be duplicates by (a) identical content_hash, (b) identical canonical_ids, (c) identical title with similar body. Output: estimated duplicate count, list of suspected duplicates for operator review.

9. **Parser-quality notes for equations/tables/sections** — for a sample of 20 papers known to contain equations, tables, or rich structure (drawn from the corpus by hand-tagging), measure: are equations preserved as readable text or mangled? are tables identifiable in the body? are section headers detectable? Output: qualitative notes per sampled paper, plus a count of papers with each issue.

### Golden QA set

A new file `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` containing 30-50 question-answer pairs. Each pair is structured:

```json
{
  "id": "qa_001",
  "question": "What is the inventory risk aversion parameter γ in Avellaneda-Stoikov?",
  "expected_paper_id": "arxiv_0709.4036",
  "expected_section_or_page": "Section 4, page 7",
  "expected_answer_substring": "γ controls the trade-off between expected profit and inventory risk",
  "category": "concept_definition",
  "difficulty": "easy"
}
```

Categories: `concept_definition`, `formula_lookup`, `empirical_finding`, `methodology`, `survey_question`. Difficulties: `easy` (single paragraph contains answer), `medium` (multiple sections required), `hard` (synthesis across multiple papers).

Cold-start: the architect curates 30 QA pairs from 10-15 papers already in the knowledge store. These are hand-written by the operator (or architect with operator review) — do NOT auto-generate QA pairs without review. Subsequent expansions of the golden set go through operator approval.

### Corpus selection rule

The benchmark runs against a **fixed, versioned corpus subset** drawn from production Layer 0 ingests:

- The first 30-50 papers ingested with `body_source=pdf` between Layer 0 ship date (2026-04-27) and the corpus freeze date (architect picks)
- Deliberately balanced: ~10 equation-heavy (microstructure theory papers), ~10 table-heavy (empirical papers with results tables), ~10 prose-heavy (surveys, conceptual papers), ~3-5 outliers (very long, multi-column, image-heavy)
- Manifest stored at `config/research_eval_benchmark_v0_corpus.json` listing source_ids and category tags
- The corpus is **never changed mid-experiment-series**. Bumping to v1 corpus requires bumping benchmark version and resetting comparison baselines.

### Benchmark report output

Two files generated per run:

1. `artifacts/research/eval_benchmark/YYYY-MM-DD_benchmark_report.md` — human-readable Markdown with all nine metrics, the recommendation among A-E, and notes on what changed since the prior report
2. `artifacts/research/eval_benchmark/YYYY-MM-DD_benchmark_report.json` — machine-readable structured output for trend tracking and CI integration

A separate `artifacts/research/eval_benchmark/baseline_v0.json` is created on the first successful run and used as the comparison anchor for all subsequent runs.

## Scope guards

- Do NOT implement PaperQA2 RAG flow — that is Layer 2
- Do NOT add new ingestion sources — that is Layer 4
- Do NOT add a multi-model evaluation gate — the multi-model decision is **gated on this benchmark's findings**. If the benchmark shows the existing eval gate is making bad calls, then a future packet adds a second model. If the benchmark shows the gate is fine, no second model.
- Do NOT auto-generate QA pairs without operator review
- Evaluation against current Layer 0 corpus only; extend to Layer 1 output when Marker production rollout lands (separate benchmark run, not separate packet)
- Do NOT run the benchmark in CI on every commit — too expensive (LLM judge calls). Manual operator-triggered for v0; CI-gated only before Layer 2 ship.

## Reference materials for architect

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — three entries are directly relevant:
   - **SciQAG** (MasterAI-EAM) — provides QA-generation methodology and the SciQAG-24D evaluation protocol. Survey notes "use to measure system, not as architectural template" — adopt the evaluation design, not their pipeline.
   - **SciDQA** (yale-nlp) — provides the format for QA pairs tied to specific paper sections/figures/equations. Reference for the golden QA set structure.
   - **PaperQA2** — the RAG flow this benchmark eventually measures. Read the citation-quality section to understand what "good" looks like.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 5 in "Adopt" specifies this layer's purpose. Constrains scope to evaluation, explicitly NOT a new RAG pipeline.
3. **Existing 31-query retrieval benchmark** — referenced in the prior stub. The architect should read whatever exists in `docs/eval/ris_retrieval_benchmark.jsonl` or equivalent and decide: extend it, replace it, or supersede it. Recommend: supersede with the v0 golden set (richer structure, paper-citation linkage) and archive the old benchmark.
4. **`[[Decision - RIS Evaluation Scoring Policy]]`** — establishes how the LLM eval gate scores documents. Inform the metric definitions (especially metric 1, off-topic rate) — there should be no contradiction between how this benchmark measures relevance and how the gate scores it.
5. **The L0 dev logs** — `docs/dev_logs/2026-04-27_ris-academic-pdf-fix.md` and `docs/dev_logs/2026-04-27_ris-docker-pdf-deps-smoke.md`. Establish the test patterns and Docker integration this packet's tests should match.

## Acceptance gates

1. **Benchmark CLI runs end to end.** `polytool research-eval-benchmark --corpus v0 --golden-set golden_qa_v0.json` returns exit 0 and produces both Markdown and JSON reports in `artifacts/research/eval_benchmark/`.
2. **All nine metrics present in report.** Each of the nine metric categories has a concrete numeric value plus supporting detail (table, list, or histogram).
3. **Recommendation produced.** The report's "Recommendation" section explicitly identifies one of A-E and gives a one-paragraph justification rooted in the metric values.
4. **Golden QA set committed.** `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` exists in the repo with 30-50 hand-curated QA pairs across all five categories and three difficulties.
5. **Corpus manifest committed.** `config/research_eval_benchmark_v0_corpus.json` exists and is referenced by the benchmark CLI.
6. **Baseline saved.** First successful run produces `artifacts/research/eval_benchmark/baseline_v0.json` for future comparison.
7. **LLM-judge OR exact-match decision documented.** The architect picks one for v0 and documents why. Recommend exact-match for v0 (cheap, deterministic, fast); upgrade to LLM-judge in a future packet if exact-match misses too much.
8. **Re-runnable.** Running the benchmark twice in a row produces deterministic metric values for everything except LLM-judge calls (which can vary). Variance for non-LLM metrics: zero.
9. **Existing tests still pass.** No existing test breaks. New benchmark tests in `tests/test_ris_eval_benchmark.py` cover at least: corpus loading, golden set loading, metric computation correctness, report generation.
10. **Dev log written.** `docs/dev_logs/2026-04-XX_ris-eval-benchmark-v0.md` documents the build, the first baseline run's findings, and the recommendation produced.

## Files expected to change/create

| File | Change | Review level |
|------|--------|-------------|
| `tools/cli/research_eval_benchmark.py` | New CLI handler. Pattern: model on `tools/cli/research_acquire.py` | Mandatory |
| `polytool/__main__.py` | Register `research-eval-benchmark` command | Mandatory |
| `packages/research/eval_benchmark/__init__.py` | New package | Mandatory |
| `packages/research/eval_benchmark/metrics.py` | Implementation of the nine metrics | Mandatory |
| `packages/research/eval_benchmark/corpus.py` | Corpus loader from manifest | Mandatory |
| `packages/research/eval_benchmark/golden_qa.py` | Golden QA set loader and validator | Mandatory |
| `packages/research/eval_benchmark/report.py` | Markdown + JSON report generator | Mandatory |
| `packages/research/eval_benchmark/recommender.py` | Logic for recommendation A-E from metric values | Mandatory |
| `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` | Golden QA pairs (architect or operator curates) | Mandatory |
| `config/research_eval_benchmark_v0_corpus.json` | Corpus manifest | Mandatory |
| `tests/test_ris_eval_benchmark.py` | New test file | Mandatory |
| `docs/dev_logs/2026-04-XX_ris-eval-benchmark-v0.md` | Dev log | Mandatory |
| `docs/runbooks/research_eval_benchmark.md` | Operator runbook for running and interpreting the benchmark | Recommended |

**Execution-critical files NOT touched:** none. This packet does not modify any execution path, ingestion path, or eval gate logic.

## Open questions for architect

1. **LLM judge vs. exact-match for answer-quality metric.** Recommend exact-match for v0. Cheaper, deterministic, faster. Upgrade in future if needed.
2. **Corpus freeze date.** Pick after this packet activates — gives Layer 0 a few weeks of production runtime to accumulate the corpus. Suggest: 2026-05-15 freeze, run benchmark 2026-05-16. Architect confirms or adjusts based on actual ingest pace.
3. **Golden QA set authorship.** Architect drafts, operator reviews and approves. Operator may rewrite questions to match domain expertise (operator knows microstructure, architect may not).
4. **Recommendation logic.** Should recommendation A-E be a hard rule-based decision tree (e.g., "if off-topic rate > 30% then A") or a soft scoring (each candidate gets a priority score)? Recommend rule-based for v0 — auditable, reproducible. Soft scoring is a future enhancement.
5. **CI integration.** v0 runs manually. Add CI gating only before Layer 2 ships — at that point, the benchmark must run before any change to retrieval can merge.
6. **Multi-model gate decision.** This is the question the benchmark answers indirectly: if metric 6 (retrieval answer quality) is poor, the cause is either the eval gate (rejecting good papers) or retrieval (failing to find them). The benchmark should help distinguish. The follow-up multi-model-evaluator packet is gated on this finding.

## Impact on roadmap

- **Activates the rest of the layer-roadmap.** Without L5, the recommendation among Layers 1/2/3/4 is operator intuition. With L5, it is data-driven.
- **Replaces the existing 31-query retrieval benchmark.** Old benchmark archived in `docs/eval/archive/`; new v0 golden set becomes the canonical reference.
- **Multi-model eval gate decision is gated on L5 output.** The decision document `[[Decision - RIS Evaluation Gate Model Swappability]]` already establishes the swappability infrastructure; adding a second model becomes a small follow-up packet if L5 says it's needed.
- **L1 (Marker production) and L5 are now parallel-buildable.** L5 measures the L0 baseline; L1 ships Marker production. Once both ship, run L5 a second time against the L1 corpus and compare. The delta is the empirical case for Layer 2.

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision (item 5)
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — Layer 0 (shipped); provides the corpus this packet measures
- [[Work-Packet - Marker Structural Parser Integration]] — Layer 1 (parallel); benchmark will be re-run after Marker ships to measure improvement
- [[Work-Packet - PaperQA2 RAG Control Flow]] — Layer 2 (gated on this packet's findings)
- [[Work-Packet - Pre-fetch SVM Topic Filter]] — Layer 3 (activation conditional on this packet's off-topic-rate metric)
- [[Work-Packet - Multi-source Academic Harvesters]] — Layer 4 (downstream)
- [[11-Scientific-RAG-Pipeline-Survey]] — SciQAG and SciDQA entries
- [[Decision - RIS Evaluation Scoring Policy]] — scoring policy this benchmark measures against
- [[Decision - RIS Evaluation Gate Model Swappability]] — multi-model decision gated on this benchmark
