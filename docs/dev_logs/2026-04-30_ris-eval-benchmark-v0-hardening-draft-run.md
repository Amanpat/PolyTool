# Dev Log: RIS Eval Benchmark v0 — Hardening and First Draft Run

**Date:** 2026-04-30
**Author:** Claude Code (Prompt B)
**Codex review:** Recommended (benchmark correctness files changed)
**Prior session:** `docs/dev_logs/2026-04-30_ris-eval-benchmark-v0-core.md` (Prompt A)
**Review addressed:** `docs/dev_logs/2026-04-30_codex-review-ris-eval-benchmark-v0.md`

---

## Objective

Apply all Codex review fixes (4 blocking, 4 major) to the benchmark
infrastructure, generate a real corpus manifest from current Layer 0 academic
data, add a corpus-discovery helper, run the benchmark in draft mode, and
verify baseline is blocked until operator QA review is complete.

---

## Codex Fixes Applied

### Blocking

**Fix 1 — Metric 6: answer correctness requires expected paper match**

`packages/research/eval_benchmark/metrics.py:_evaluate_retrieval_pair()`

Extracted retrieval evaluation into a pure helper. `answer_found` is now only
set to `True` when the chunk containing the expected answer substring also
belongs to `expected_paper_id`. Previously any top-5 chunk match counted.
Added per-question detail: `matched_doc_id`, `matched_file_path`,
`matched_rank`, `answer_match_rank`, `top_5_doc_ids`.

**Fix 2 — Metric 7: full traceability subcounts and per-pair detail**

`compute_metric_7_citation_traceability()` now emits `traceable_count`,
`evaluated_count`, `missing_source_count`, `missing_page_count`,
`missing_passage_count`, `traceability_rate_pct`, and per-pair `detail` rows
with `has_source`, `has_page`, `has_passage`, `traceable`, `missing_reasons`.
A result is traceable only when: expected paper retrieved AND source URL/file
path present AND expected answer substring in chunk text.

**Fix 3 — Metric 9: filter to sampled_categories, deterministic issue counts**

`compute_metric_9_parser_quality_notes()` now filters docs to only those whose
`_meta.category` is in `sampled_categories` (injected from corpus manifest by
`compute_all_metrics()`). Reports: `equation_not_parseable_count`,
`table_not_detectable_count`, `section_headers_missing_count`,
`missing_page_count`, plus rates over the assessable denominator.
`skipped_abstract_fallback_count` tracks in-scope docs excluded for being
abstract-only. Docs with `category=None` or outside the sampled set are now
correctly excluded.

**Fix 4 — Report: triggered_rules persisted in JSON and Markdown**

`generate_markdown_report()`, `generate_json_report()`, `write_reports()` now
accept `triggered_rules: Optional[List[str]]`. JSON includes
`recommendation.triggered_rules`. Markdown shows a "Triggered rules" subsection
listing each fired rule, or "No threshold rules fired" when empty. The CLI
passes `rec.triggered_rules` to all three report paths.

### Major

**Fix 5 — Metric 1: title + abstract + body keyword check**

`compute_metric_1_off_topic_rate()` now checks `title + _meta.abstract +
_meta.body[:2000]` against seed keywords (previously title only). Also
validates that `seed_topic_keywords` is non-empty; returns `status="error"`
for empty or blank-only lists.

**Fix 6 — Metric 8: canonical id and similar-body/title duplicates**

`compute_metric_8_duplicate_dedup_behavior()` now groups by `doi`, `arxiv_id`,
and `canonical_id` metadata fields to detect canonical-id duplicates.
Adds `similar_title_body_dupes` via title-prefix + body-prefix-hash grouping.
Reports `canonical_id_dupes`, `similar_title_body_dupes` in value; detail rows
carry canonical_id or title_prefix.

**Fix 7 — Metric 5: review_priority field on suspicious records**

`_review_priority(doc)` helper classifies each suspicious record:
- `high`: chunk_count==0 OR body_source==abstract_fallback OR body_length<100
- `medium`: chunk_count in [1,2] AND body_source==pdf
- `low`: otherwise
Each suspicious record in metric 5 detail now includes `review_priority`.

**Fix 8 — Missing source ids: detection in compute_all_metrics()**

`compute_all_metrics()` now compares manifest source_ids to loaded document
ids and populates `AllMetricsResult.missing_source_ids` and
`AllMetricsResult.manifest_entries`. The CLI warns to stderr on any missing
ids; `--strict` mode exits 1 when missing ids are present.

---

## Corpus Discovery Helper Added

`tools/cli/research_eval_benchmark.py: _run_discover_corpus()`

```bash
python -m polytool research-eval-benchmark --discover-corpus
```

Lists all academic records in the KnowledgeStore with source_id, title,
chunk_count, body_source, and body_length. Outputs a human-readable table
plus full JSON array. Used to populate corpus manifests.

---

## Corpus Manifest Generated from Real Data

**File:** `config/research_eval_benchmark_v0_corpus.draft.json`

Queried `kb/rag/knowledge/knowledge.sqlite3` and found **39 academic records**.
Selected **23 entries** for the draft corpus:

| Category | Count | Purpose |
|----------|-------|---------|
| High-quality (chunk≥9, pdf body) | 17 | Core evaluation corpus |
| Outlier (off-topic for metric 1 test) | 3 | Validate off-topic detection |
| Low-chunk stubs (chunk≤4) | 3 | Validate metric 5 suspicious records |
| **Total** | **23** | — |

**Excluded:** 16 records (audio/speech/climate challenge papers clearly outside
prediction-markets domain scope).

**Insufficiency note:** Target is 30-50 reviewed QA pairs and 30-50 corpus
entries. Current Layer 0 has 17 topic-relevant high-quality papers; the gap
to 30+ can be closed with additional ingestion (Layer 0 continues to grow).
This is documented in the corpus manifest description.

**Duplicate test case:** Entry `0838c7de...` is intentionally included as a
near-duplicate of `0c8b3c3a...` (same title, chunk=1 vs chunk=39) to exercise
metric 8 dedup detection.

---

## Draft Report Results (2026-04-30)

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

**Key draft results:**

| Metric | Value | Notes |
|--------|-------|-------|
| Corpus size | 23 | All 23 manifest entries found in DB |
| Missing source IDs | 0 | All manifest IDs resolved |
| Off-topic rate | 30.43% (7/23) | Triggers Rule A (>30%) |
| Fallback rate | 0.0% | All docs have pdf body |
| Retrieval P@5 | 0.0 | Draft QA has placeholder expected_paper_id |
| Median chunk count | 25.0 | Healthy |
| Triggered rules | A, C, D | A wins (priority order) |

**Recommendation:** A — Pre-fetch relevance filtering

Rule A fires because the 3 outlier papers (materials science, medical, 
e-commerce) push the off-topic rate to 30.43% (marginally above threshold).
After operator removes/re-categorizes outlier entries from the final corpus,
this rate will drop below 30%.

Rule C fires because draft QA has placeholder `REPLACE_WITH_DOC_ID_OR_FILE_PATH`
as `expected_paper_id` — nothing matches in retrieval. Will resolve after QA
review.

Rule D fires because metric 9's equation-parseable heuristic (checks for `=`,
`\(`, `\[` in body text) triggers on most equation-heavy papers whose body text
stores equations as plain prose without LaTeX markers. This is a known
limitation of the body_text heuristic on text-extracted PDFs.

---

## Baseline Block Verified

```bash
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json \
  --save-baseline --dry-run
```

Output:
```
WARNING: QA set is NOT operator-reviewed (review_status='operator_review_required'). Results are indicative only.
ERROR: --save-baseline requires reviewed QA. Operator must review the QA set and set review_status='reviewed'.
```
Exit code: 1. `artifacts/research/eval_benchmark/baseline_v0.json` does not exist.

---

## Tests

**Benchmark test suite:** 74 passed, 0 failed (was 45; added 29 new tests)

New test classes added to `tests/test_ris_eval_benchmark.py`:
- `TestMetric6AnswerOnlyInExpectedPaper` — 4 tests (blocking fix 1)
- `TestMetric5ReviewPriority` — 5 tests (major fix 7)
- `TestMetric8ExtendedDuplicates` — 4 tests (major fix 6)
- `TestMetric9CategoryFiltering` — 4 tests (blocking fix 3)
- `TestReportTriggeredRules` — 6 tests (blocking fix 4)
- `TestMissingSourceIds` — 2 tests (major fix 8)
- `TestMetric1AbstractKeyword` — 4 tests (major fix 5)

**Full regression suite:** 2397 passed, 1 failed (pre-existing
`test_ris_claim_extraction.py::test_each_claim_has_required_fields`,
`heuristic_v2_nofrontmatter != heuristic_v1`, present before this session).

**Commands run:**
```bash
python -m pytest tests/test_ris_eval_benchmark.py -x -q --tb=short
# 74 passed in 0.42s

python -m polytool research-eval-benchmark --help
# exit 0

python -m polytool research-eval-benchmark --corpus v0 --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json --dry-run
# exit 0, 23 entries

python -m polytool research-eval-benchmark --discover-corpus
# exit 0, 39 academic records listed

python -m polytool research-eval-benchmark --corpus v0 --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json
# exit 0, draft reports written
```

---

## Codex Review Summary

Tier: Recommended (benchmark correctness files — metrics.py, report.py, CLI)

Issues found by prior Codex review (Prompt A):
- 4 blocking, 4 major, 1 non-blocking

Issues addressed in this session:
- 4 blocking fixed
- 4 major fixed
- 1 non-blocking: no action required per Codex guidance

---

## L5 Readiness Assessment

**L5 is NOT ready to be marked complete.** Remaining operator steps:

1. **QA review (REQUIRED before baseline):**
   - Replace all `REPLACE_WITH_DOC_ID_OR_FILE_PATH` in
     `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`
   - Verify each `expected_answer_substring` against real body text in the DB
   - Add QA pairs to reach 30-50 target (current: 5 placeholder)
   - Change `review_status` to `"reviewed"` and save as `golden_qa_v0.json`

2. **Corpus review (RECOMMENDED before baseline):**
   - Review outlier category entries — remove if not needed, or leave for
     off-topic metric testing
   - Promote draft to `config/research_eval_benchmark_v0_corpus.json`

3. **Baseline creation (AFTER QA review):**
   ```bash
   python -m polytool research-eval-benchmark \
     --corpus config/research_eval_benchmark_v0_corpus.json \
     --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
     --save-baseline
   ```

4. **Lexical index (for metrics 6 and 7):**
   ```bash
   python -m polytool rag-refresh
   ```
   Then re-run benchmark to get P@5 and citation traceability values.

---

## Operator Review Checklist

- [ ] Read `artifacts/research/eval_benchmark/2026-04-30_benchmark_report_draft.md`
- [ ] Review 23 corpus entries in `config/research_eval_benchmark_v0_corpus.draft.json`
      — confirm source_ids are correct, categories are accurate
- [ ] Replace placeholder `expected_paper_id` values in
      `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`
- [ ] Verify `expected_answer_substring` values appear in paper body text
- [ ] Add QA pairs to reach 30+ (target 30-50)
- [ ] Run `python -m polytool rag-refresh` to build lexical index
- [ ] Re-run benchmark after QA review to get real P@5
- [ ] When satisfied: change `review_status` to `"reviewed"` and run `--save-baseline`
- [ ] Do NOT create `baseline_v0.json` before QA review is complete

---

## Open Questions

1. **Metric 9 / Rule D:** The heuristic for `equation_parseable` (checks for
   `=`, `\(`, `\[` in body text) fires for 100% of equation_heavy papers in
   the draft run. This may be a false alarm — the papers have equations but
   plain-text extraction strips LaTeX markers. Operator should verify whether
   Rule D represents a real Marker rollout signal or a heuristic limitation.
   A better heuristic could check for numeric expressions or MathML patterns.

2. **Corpus size:** 17 high-quality topic-relevant papers is below the 30-50
   target. More Layer 0 ingestion is needed. Re-run `--discover-corpus` after
   next ingestion cycle to identify new candidates.

3. **Off-topic 30.43%:** Triggered by the 3 intentional outlier entries. After
   corpus review (remove or keep outliers), the off-topic rate will change.
   If outliers are removed, Rule A may not fire in the final baseline run.
