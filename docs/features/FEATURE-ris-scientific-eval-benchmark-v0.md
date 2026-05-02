# Feature: RIS Scientific RAG Evaluation Benchmark v0

**Status:** Complete — baseline locked 2026-05-02  
**Track:** Research Intelligence System (L5)  
**Baseline artifact:** `artifacts/research/eval_benchmark/baseline_v0.json`

---

## What This Feature Is

A structured benchmark that measures the quality of the RIS corpus and retrieval
pipeline across nine metrics, producing a prioritized letter-grade recommendation
(A–E or NONE) indicating the highest-priority pipeline improvement.

This is **L5** in the RIS layer numbering:
- L0: Ingestion (research-acquire, research-ingest)
- L1: Marker structural parser (experimental, optional)
- L2: Chunking and retrieval infrastructure
- L3: Pre-fetch relevance filtering (next recommended work)
- L4: Retrieval quality tuning
- L5: Evaluation benchmark (this feature)

---

## Command Sequence Used to Create v0 Baseline

```bash
# Step 1: Run scoped lexical refresh (indexes only corpus papers)
python -m polytool research-eval-benchmark --corpus v0 --refresh-lexical

# Step 2: Verify reviewed golden QA loads cleanly
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
  --dry-run

# Step 3: Save baseline
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
  --save-baseline \
  --output-dir artifacts/research/eval_benchmark
```

---

## Scoped Lexical Refresh Result

Run on 2026-05-02:

- Corpus entries: 23
- Bodies found in raw_source_cache: 22 (86.96% pdf body source)
- Indexed: 22 papers
- Skipped: 1 (`d744370b...` — Prediction Market Microstructure and Informed Trading — no body
  text in cache; stub entry with chunk_count=1 and body_source=unknown)
- Elapsed: ~3–4 seconds

---

## Golden QA Set

- **File:** `tests/fixtures/research_eval_benchmark/golden_qa_v0.json`
- **Pairs:** 35 reviewed pairs
- **Review status:** `reviewed`
- **Papers covered:** 10 distinct papers from the 23-paper corpus
- **Review method:** Operator review pass with 4 weak-substring repairs on 2026-05-02.
  The review was performed with direct verification of all 35 substrings against
  `artifacts/research/raw_source_cache/academic/*.json` payload.body_text.
  See `docs/dev_logs/2026-05-02_ris-eval-benchmark-golden-qa-finalized.md`.

> **Important:** This one-time review used a bulk-accept pass (all 35 candidates accepted
> after targeted fixes to 4 weak rows). This was appropriate for establishing the initial
> baseline, not a template for future QA set reviews. Future QA additions must follow the
> full operator review protocol in `docs/runbooks/research_eval_benchmark.md` Step 2.

---

## Baseline Metrics (v0 — 2026-05-02)

| # | Metric | Value | Status |
|---|--------|-------|--------|
| 1 | Off-topic rate | 30.43% (7/23) | OK — at threshold; Rule A fired |
| 2 | Body source distribution | 20 pdf / 3 unknown (86.96% pdf) | OK |
| 3 | Fallback rate | 0.0% | OK |
| 4 | Chunk count distribution | median=25, mean=22.35, p5=1, p95=44.4 | OK |
| 5 | Low-chunk suspicious records | 3 papers with chunk_count=1, no body | OK (flagged) |
| 6 | Retrieval P@5 | 1.0 (35/35 papers found at rank ≤5) | OK — perfect paper retrieval |
| 7 | Citation traceability | 11.43% (4/35) — all missing page numbers | OK (flagged) |
| 8 | Duplicate/dedup | 0 hash dupes, 1 title dupe | OK |
| 9 | Parser quality (equation_heavy) | 100% not parseable — Rule D fired (secondary) | OK |

**Recommendation: A — Pre-fetch Relevance Filtering**

Both Rule A (off_topic_rate > 30%) and Rule D (equation_heavy parseable < 70%) fired.
Rule A takes priority per the recommendation hierarchy. Rule D is documented below.

---

## Interpretation

### P@5 = 1.0 (Metric 6) — Oracle retrieval is working

Every one of the 35 QA papers was found within the top 5 BM25 retrieval results.
This means the scoped lexical index is correctly built and indexed papers are findable.

However, the **answer_correctness_rate** (whether the expected answer substring appears
in the retrieved chunk text) is only 11.43% (4/35). The search is done with the answer
substring as the query, not the question text — so this measures whether the answer chunk
is surfaced *and* the substring appears verbatim in the chunk window returned. Low
answer_correctness_rate with high P@5 indicates BM25 is routing to the right paper but
the exact passage containing the answer is not the top-ranked chunk. This is a chunking
and ranking limitation, not an indexing failure.

### 30.43% off-topic rate (Metric 1) — Expected at this stage

7 of 23 corpus papers are flagged off-topic by the seed-topic classifier. Three of those
were intentionally included as outlier/test entries when the draft corpus was built. The
remaining four are borderline. This rate will improve once pre-fetch relevance filtering
(Recommendation A) is implemented.

The 7 off-topic papers:
- Hastelloy-X fatigue life prediction (materials science — clearly off-topic)
- Head/neck cancer outcome prediction (medical ML — clearly off-topic)
- Indian Financial Market cross-correlation (borderline — microstructure but not PM)
- E-commerce delayed conversion modeling (borderline)
- How Market Ecology Explains Market Malfunction (relevant to market microstructure — potential false positive)
- On a Class of Diverse Market Models (stochastic portfolio theory — borderline)
- The Inelastic Market Hypothesis (market microstructure — potential false positive)

### Rule D (Metric 9) — Heuristic, secondary

Rule D fired because 100% of the 8 equation_heavy papers show `equation_parseable=False`.
This is expected behavior with pdfplumber (plain-text extraction): LaTeX/MathML equations
are flattened into Unicode glyphs and character sequences that cannot be detected as
structured equation objects. This is NOT a Marker rollout signal — pdfplumber is doing
exactly what it's supposed to do, and Marker is already shipped as optional/experimental
(see `docs/features/ris-marker-structural-parser-scaffold.md`).

Rule D reflects a **heuristic limitation**: the "equation parseable" flag checks for
structured equation detection in extracted text, which pdfplumber cannot provide.
Do not treat Rule D as a blocker or priority action ahead of Recommendation A.

### 3 no-body papers (Metric 5)

Three corpus papers have chunk_count=1 and body_source=unknown — they are stub entries
with no PDF body text in the raw source cache:
- High frequency market microstructure noise estimates and liquidity measures (0838c7de...)
- The Homogenous Properties of Automated Market Makers (bad51e5d...)
- Prediction Market Microstructure and Informed Trading (d744370b...)

These should be re-acquired with `research-acquire --url <url>` in a future corpus
maintenance pass. They don't block the baseline or Recommendation A.

---

## Output Artifacts

| Artifact | Path |
|----------|------|
| Baseline JSON | `artifacts/research/eval_benchmark/baseline_v0.json` |
| Benchmark report (Markdown) | `artifacts/research/eval_benchmark/2026-05-02_benchmark_report.md` |
| Benchmark report (JSON) | `artifacts/research/eval_benchmark/2026-05-02_benchmark_report.json` |
| Reviewed golden QA | `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` |
| Draft corpus manifest | `config/research_eval_benchmark_v0_corpus.draft.json` |

---

## Limitations

1. **1 no-body placeholder in QA coverage** — qa_029 maps to `0c8b3c3a...` which has
   a body in cache, but `0838c7de...` (same-title stub entry) has no body and would
   return empty retrieval for any QA pair targeting it. No QA pairs currently target
   the three no-body stubs, so this does not affect P@5.

2. **Corpus includes off-topic outliers** — 7/23 papers are off-topic, inflating Rule A.
   Three were included intentionally to test the off-topic detector; the other four
   crept in during Layer 0 ingestion. Relevance filtering (Recommendation A) is the
   correct remedy.

3. **Rule D is a heuristic** — The "equation parseable" check uses plain-text heuristics
   that always fail for pdfplumber output. It does NOT indicate parsing failures;
   it indicates that structured math representation is unavailable. This is expected
   at the current extraction layer and is not actionable without a production Marker rollout.

4. **Citation traceability at 11.43%** — All 35 QA pairs lack page numbers; 31 also
   lack a stored passage quote. The traceability rate measures full attribution chains.
   Adding page annotations to QA pairs would significantly improve this metric without
   changing retrieval quality.

---

## Next Recommended Work

**Recommendation A: Pre-fetch Relevance Filtering (Layer 3)**

Filter papers at the point of ingestion using a seed-topic relevance scorer
so off-topic papers do not enter the corpus. Targets:

- Off-topic rate drops below 10%
- Rule A no longer fires
- Corpus grows in quality without growing in size

Scope: modify the research-acquire pipeline to score candidate papers against
PolyTool's seed topic list (prediction markets, market microstructure, market
making, quantitative finance) before committing them to the KnowledgeStore.
A simple keyword or embedding-similarity pre-filter is sufficient for v1.
