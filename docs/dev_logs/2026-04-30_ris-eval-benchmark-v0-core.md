# Dev Log: RIS Eval Benchmark v0 Core Infrastructure

**Date:** 2026-04-30
**Author:** Claude Code
**Codex review:** Skip (docs + tests + new feature package, no mandatory-review files touched)

---

## Objective

Implement the Scientific RAG Evaluation Benchmark v0 infrastructure for the
Research Intelligence System. This provides nine metrics to assess corpus
quality and retrieval accuracy, a rule-based recommendation engine, and a CLI
for operator use.

---

## Files Created

### Core package — `packages/research/eval_benchmark/`

| File | Purpose |
|------|---------|
| `__init__.py` | Empty package marker |
| `corpus.py` | CorpusManifest + CorpusEntry dataclasses; `load_corpus_manifest()` with validation |
| `golden_qa.py` | GoldenQASet + QAPair dataclasses; `load_golden_qa()` + `is_reviewed()` |
| `metrics.py` | Nine `compute_metric_N_*()` functions; `compute_all_metrics()` aggregator; `AllMetricsResult` |
| `report.py` | `generate_markdown_report()`, `generate_json_report()`, `write_reports()` |
| `recommender.py` | `recommend()` rule engine; A-E priority ladder; `RecommendationResult` |

### CLI — `tools/cli/research_eval_benchmark.py`

Full argparse CLI supporting:
- `--corpus PATH` (or `v0` shorthand for auto-discovery)
- `--golden-set PATH` (or `v0` shorthand; optional)
- `--output-dir`, `--db`, `--lexical-db`
- `--dry-run` — validate inputs only
- `--strict` — refuse unreviewed QA
- `--save-baseline` — write `baseline_v0.json` (requires reviewed QA)
- `--json` — append machine-readable JSON summary to stdout
- Exit codes: 0=success, 1=validation error, 2=computation error

### Modified — `polytool/__main__.py`

Added:
- `research_eval_benchmark_main = _command_entrypoint("tools.cli.research_eval_benchmark")`
- `"research-eval-benchmark": "research_eval_benchmark_main"` in `_COMMAND_HANDLER_NAMES`
- Usage line in `print_usage()` Research Intelligence section

### Fixture files

| File | Status |
|------|--------|
| `config/research_eval_benchmark_v0_corpus.draft.json` | Draft with placeholder `source_id` — operator must populate |
| `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json` | Draft with 5 placeholder QA pairs — operator must review |

### Tests — `tests/test_ris_eval_benchmark.py`

37 offline tests covering all five modules and CLI policy.

### Runbook — `docs/runbooks/research_eval_benchmark.md`

Covers all six operator steps: corpus population, QA review, dry-run, full
run, recommendation interpretation, and baseline creation.

---

## Verification

Commands run after implementation:

```bash
python -m pytest tests/test_ris_eval_benchmark.py -v --tb=short
python -m polytool research-eval-benchmark --help
python -m polytool research-eval-benchmark \
  --corpus config/research_eval_benchmark_v0_corpus.draft.json \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json \
  --dry-run
```

See task report for exact counts and output.

---

## What Is Draft vs Final

### Draft (operator action required before use)

- `config/research_eval_benchmark_v0_corpus.draft.json` — placeholder `source_id`
  values must be replaced with real KnowledgeStore document IDs
- `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json` — placeholder
  `expected_paper_id` values must be replaced with real IDs; `review_status`
  must be changed to `"reviewed"` after operator review

### Final (ready to use)

- All Python modules in `packages/research/eval_benchmark/`
- CLI in `tools/cli/research_eval_benchmark.py`
- `polytool/__main__.py` registration
- Test suite in `tests/test_ris_eval_benchmark.py`
- Runbook in `docs/runbooks/research_eval_benchmark.md`

---

## Design Notes

### Metrics requiring lexical DB (6, 7)

Metrics 6 and 7 gracefully degrade to `status="not_available"` if the lexical
DB does not exist or the `packages.polymarket.rag.lexical` import fails. This
allows the benchmark to run even when the FTS5 index has not been built yet.
Run `python -m polytool rag-refresh` to build it.

### Category info in metric 9

The KnowledgeStore `source_documents` table does not store the corpus category
(`equation_heavy`, etc.) — that lives in the corpus manifest. `compute_all_metrics()`
injects the category from the manifest into the doc's `_meta` dict before
calling metric 9, so the heuristics have access to it.

### DB query pattern

Metrics load documents directly via `sqlite3.connect()` against the
KnowledgeStore DB (not through the `KnowledgeStore` class) to avoid
importing the full RIS stack. This keeps the eval benchmark package
dependency-light.

### Recommendation priority

Rules are evaluated in A→B→C→D→E order. The first triggered rule wins.
All triggered rules are collected in `triggered_rules` for transparency,
even when a higher-priority rule is already the winner.

---

## Remaining Steps for Operator

1. **Populate corpus manifest:** Query the KnowledgeStore for real `source_id`
   values and create `config/research_eval_benchmark_v0_corpus.json` from
   the draft. Aim for 15-25 representative papers.

2. **Review golden QA:** Edit
   `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`:
   - Replace `REPLACE_WITH_DOC_ID_OR_FILE_PATH` with actual doc IDs
   - Verify `expected_answer_substring` actually appears in each paper's body
   - Add 5-15 more QA pairs for better P@5 coverage
   - Change `review_status` to `"reviewed"`
   - Save as `golden_qa_v0.json`

3. **Build lexical index** (if not already current):
   ```bash
   python -m polytool rag-refresh
   ```

4. **Run first full benchmark:**
   ```bash
   python -m polytool research-eval-benchmark --corpus v0 --golden-set v0
   ```

5. **Save baseline** once QA is reviewed:
   ```bash
   python -m polytool research-eval-benchmark \
     --corpus v0 --golden-set v0 --save-baseline
   ```

---

## Open Questions / Blockers

- None. The benchmark infrastructure is complete and offline-functional.
  The only dependency is operator action to populate real corpus+QA data
  before a meaningful baseline can be saved.
