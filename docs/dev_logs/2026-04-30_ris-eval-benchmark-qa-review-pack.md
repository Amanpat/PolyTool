# Dev Log: RIS Eval Benchmark v0 — QA Review Pack Preparation

**Date:** 2026-04-30
**Author:** Claude Code (Prompt C)
**Prior session:** `docs/dev_logs/2026-04-30_ris-eval-benchmark-v0-hardening-draft-run.md` (Prompt B)

---

## Objective

Expand `golden_qa_v0.draft.json` from 5 placeholder pairs to 35 candidate QA pairs with
verified `expected_answer_substring` values. Produce an operator Markdown review table.
Do NOT mark QA reviewed, do NOT create `baseline_v0.json`.

---

## Corpus Count Used

**23 entries** from `config/research_eval_benchmark_v0_corpus.draft.json`, confirmed via:

```
python -m polytool research-eval-benchmark --discover-corpus
# 39 academic records in KnowledgeStore; 23 selected for corpus
```

---

## Key Discovery: Where Body Text Lives

The `source_documents.metadata_json` field stores only body metadata (`body_source`,
`body_length`, `page_count`) — NOT the body text itself. The lexical index
(`kb/rag/lexical/lexical.sqlite3`) has no academic paper chunks (only artifact/dossier/kb
doc_types are indexed). The actual body text lives in:

```
artifacts/research/raw_source_cache/academic/<hash>.json
└── payload.body_text   ← full extracted PDF text (80k-89k chars for largest papers)
```

**20 out of 23 corpus papers** have body text in the cache. The 3 missing are the stub
entries with `chunk_count <= 1` and `body_source=unknown` (low-chunk stubs added for
metric 5 testing).

This also means **metric 6 (P@5) will remain 0 until `rag-refresh` is run** to index
academic paper chunks into the lexical store. The `rag-refresh` command indexes files
from `kb/` and `artifacts/` directories but does not currently read source_documents body
from the raw_source_cache. This is a gap that should be surfaced to the operator.

---

## QA Pair Count Created

**35 candidate pairs**, up from 5 placeholders. Distribution:

| Paper | Pairs |
|-------|-------|
| SoK: Market Microstructure for DePMs (b1982ae0) | 7 |
| Toward Black Scholes for PM (8cebfdb3) | 6 |
| Limit Order Book Dynamics (e3578757) | 3 |
| Semi Markov model for microstructure (68acefe9) | 3 |
| Interpretable Hypothesis-Driven Trading (64d01f09) | 4 |
| TradeFM generative foundation model (89b902e6) | 4 |
| HF microstructure noise estimates (0c8b3c3a) | 2 |
| How Market Ecology Explains Malfunction (6e911b4f) | 3 |
| Systemic Risk / Hawkes Flocking (af8935f6) | 2 |
| FX Market Microstructure / WM Fix (40fd58b7) | 1 |
| **Total** | **35** |

Category breakdown: concept_definition=10, methodology=10, empirical_finding=12,
formula_lookup=1, survey_question=2.

---

## Verification Method for Answer Substrings

**Primary:** Python `str.lower() in body.lower()` search against
`artifacts/research/raw_source_cache/academic/<hash>.json → payload.body_text`.

**Cache file mapping:** source_url from `source_documents` → arxiv URL → matched to cache
file `payload.url` field.

**Supplementary:** For full abstract text beyond the 500-char metadata_json truncation,
arxiv abstract pages were fetched via ScraplingServer (HTML content).

**Result:** 35/35 substrings verified (100%). One initial failure (qa_025) was corrected —
the phrase "scale-invariant features and a universal tokenization scheme" spans a PDF
line break; replaced with "universal tokenization scheme" which is on a single line.

**Verification command:**
```python
# Run in repo root
python -c "
import json, os, sqlite3
# [see body of verification script in this log's source session]
# Result: Verified: 35/35 (100%)
"
```

**Note on qa_012:** The substring `unifying\nstochastic kernel that options gained from Black`
contains a literal newline from the PDF body text. This will match in BM25 lexical search
only if the FTS engine normalizes whitespace. Operator should flag for possible cleanup.

---

## Draft Benchmark Output

**Command run:**
```bash
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json \
  --output-dir artifacts/research/eval_benchmark
```

**Output files:**
- `artifacts/research/eval_benchmark/2026-04-30_benchmark_report_draft.md`
- `artifacts/research/eval_benchmark/2026-04-30_benchmark_report_draft.json`
- `artifacts/research/eval_benchmark/QA_OPERATOR_REVIEW_v0.md` ← new operator review table

**Key draft results:**

| Metric | Value | Notes |
|--------|-------|-------|
| Corpus size | 23 | All 23 manifest entries found in DB |
| QA pairs loaded | 35 | Expanded from 5 placeholder pairs |
| Off-topic rate | 30.43% (7/23) | Triggers Rule A — 3 outlier entries push above 30% |
| Fallback rate | 0.0% | All docs have pdf body_source |
| Retrieval P@5 | 0.0 | Lexical index has no academic chunks; rag-refresh required |
| Median chunk count | 25.0 | Healthy |
| Triggered rules | A, C, D | A highest priority — recommendation: pre-fetch relevance filter |

---

## Baseline Block Result

```bash
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json \
  --save-baseline --dry-run
# Exit code: 1
# ERROR: --save-baseline requires reviewed QA. Operator must review the QA set and set review_status='reviewed'.
```

`artifacts/research/eval_benchmark/baseline_v0.json` does NOT exist. Block is working.

---

## Tests Run

```bash
python -m pytest tests/test_ris_eval_benchmark.py -x -q --tb=short
# 74 passed in 0.42s
```

No regressions.

---

## Operator Review Instructions

1. **Read** `artifacts/research/eval_benchmark/QA_OPERATOR_REVIEW_v0.md`
2. For each of 35 rows: Accept, Edit (provide corrected substring), or Reject
3. Edit `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`:
   - Apply all edits/rejections from the review table
   - Remove rejected pairs
   - Change `review_status` from `"operator_review_required"` to `"reviewed"`
4. Save as `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` (no `.draft.`)
5. Run `python -m polytool rag-refresh` to populate lexical index with academic paper chunks
6. Re-run benchmark to get real P@5 values:
   ```bash
   python -m polytool research-eval-benchmark --corpus v0 \
     --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json
   ```
7. When satisfied: run with `--save-baseline` to create `baseline_v0.json`

**Do NOT** create `golden_qa_v0.json` or `baseline_v0.json` before completing steps 1-4.

---

## Open Questions for Operator

1. **qa_012 newline substring:** The substring contains a literal `\n` from PDF line
   wrapping. Consider replacing with a shorter clean phrase like "stochastic kernel that
   options gained".

2. **Corpus outliers (3 papers):** The 3 outlier papers (materials science, medical,
   e-commerce) push the off-topic rate to 30.43% triggering Rule A. After corpus review,
   if outliers are removed, Rule A may not fire in the final baseline run. The outliers
   serve a metric-1 testing purpose — operator should decide if they stay.

3. **rag-refresh gap:** The `rag-refresh` command indexes from `kb/` and `artifacts/`
   directories but the academic paper body text is in `raw_source_cache/academic/` which
   is under `artifacts/`. It's possible rag-refresh already handles this path — confirm
   by running `rag-refresh` and checking if academic doc_type chunks appear in the lexical
   index after.

4. **Corpus size below target:** 17 high-quality topic-relevant papers is below the 30-50
   target. Additional ingestion needed. Re-run `--discover-corpus` after next ingest cycle.

---

## Codex Review Summary

Tier: Skip (QA fixture expansion and report generation — docs/fixtures, not strategy/execution code)

---

## L5 Readiness

**Still NOT ready to mark L5 complete.** QA review is the remaining blocker.

Remaining steps before L5:
1. Operator review of 35 QA pairs (this packet provides the materials)
2. `golden_qa_v0.json` creation (after review)
3. `rag-refresh` to populate lexical index
4. `--save-baseline` run to create `baseline_v0.json`
