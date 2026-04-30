# Research Eval Benchmark v0 — Operator Runbook

## What This Benchmark Measures

The Scientific RAG Evaluation Benchmark v0 measures the quality of the RIS
(Research Intelligence System) corpus and retrieval pipeline across nine metrics:

| # | Metric | What It Tests |
|---|--------|---------------|
| 1 | Off-topic rate | Are ingested papers relevant to PolyTool's seed topics? |
| 2 | Body source distribution | How many papers have full PDF bodies vs abstract fallbacks? |
| 3 | Fallback rate | What fraction of papers fell back to abstract-only parsing? |
| 4 | Chunk count distribution | Is the corpus chunked adequately for retrieval? |
| 5 | Low-chunk suspicious records | Are there parse failures or stub documents? |
| 6 | Retrieval answer quality | Does lexical search find the right paper (P@5)? |
| 7 | Citation traceability | Can retrieved chunks be linked back to source documents? |
| 8 | Duplicate/dedup behavior | Are there content-hash or title-level duplicates? |
| 9 | Parser quality notes | Are equation-heavy and table-heavy papers correctly parsed? |

The benchmark outputs a prioritized recommendation (A through E, or NONE):

- **A**: Pre-fetch relevance filtering (Layer 3) — too many off-topic papers
- **B**: Old-paper re-ingest cleanup — too many abstract-fallback papers
- **C**: PaperQA2-style retrieval (Layer 2) — retrieval P@5 below threshold
- **D**: Marker production validation (Layer 1) — parser quality issues
- **E**: Chunking changes — median chunk count too low
- **NONE**: System healthy, no action threshold exceeded

---

## Prerequisites

- RIS Layer 0 ingests have run and the KnowledgeStore DB is populated:
  `kb/rag/knowledge/knowledge.sqlite3`
- Optionally, the FTS5 lexical DB is built:
  `kb/rag/lexical/lexical.sqlite3`
  (metrics 6 and 7 show as `not_available` without it)
- Python environment: `python -m polytool --help` succeeds without import errors

---

## Step 1: Populate the Corpus Manifest

The draft manifest lives at:
`config/research_eval_benchmark_v0_corpus.draft.json`

You need to replace the placeholder entries with real `source_id` values from
the KnowledgeStore. To find ingested document IDs:

```bash
# List recently ingested documents
python -m polytool research-stats summary

# Or query directly
sqlite3 kb/rag/knowledge/knowledge.sqlite3 \
  "SELECT id, title, source_family FROM source_documents LIMIT 20"
```

For each paper you want to include in the evaluation corpus:

1. Find its `id` in the KnowledgeStore (SHA-256 hex string)
2. Copy `config/research_eval_benchmark_v0_corpus.draft.json` to
   `config/research_eval_benchmark_v0_corpus.json`
3. Replace `"REPLACE_WITH_REAL_SHA256_ID"` with the actual document ID
4. Set the correct `category` (one of: `equation_heavy`, `table_heavy`,
   `prose_heavy`, `outlier`, or omit for `null`)
5. Add relevant `tags` for filtering

Aim for at least 10-20 papers covering the seed topic keywords:
prediction market, avellaneda-stoikov, kelly criterion, market microstructure,
informed trading, adverse selection, bid-ask spread, etc.

---

## Step 2: Create and Review the Golden QA Set

The draft QA set lives at:
`tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`

To create a reviewed QA set:

1. Copy the draft to `tests/fixtures/research_eval_benchmark/golden_qa_v0.json`
2. Replace each `"REPLACE_WITH_DOC_ID_OR_FILE_PATH"` with the actual document ID
   from the KnowledgeStore for the paper that answers each question
3. Edit `expected_answer_substring` to be a short, distinctive phrase that
   **actually appears** in the paper's body text
4. Edit `expected_section_or_page` to the correct section or page number
5. Add more QA pairs as needed (aim for 10-20 pairs minimum for meaningful P@5)
6. Change `"review_status": "operator_review_required"` to `"review_status": "reviewed"`

### QA category reference

| Category | Use for |
|----------|---------|
| `concept_definition` | "What is X?" questions |
| `formula_lookup` | "What is the formula for X?" questions |
| `empirical_finding` | "What did the paper find about X?" questions |
| `methodology` | "How does X work?" questions |
| `survey_question` | Questions that span multiple papers |

### QA difficulty reference

| Difficulty | Use for |
|------------|---------|
| `easy` | Answer appears verbatim; distinctive keyword |
| `medium` | Answer requires paraphrasing; multiple candidate chunks |
| `hard` | Answer requires synthesis; answer substring is non-obvious |

---

## Step 3: Run the Benchmark

### Dry-run (validate inputs only, no metrics computed)

```bash
python -m polytool research-eval-benchmark \
  --corpus config/research_eval_benchmark_v0_corpus.json \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
  --dry-run
```

Expected output:
```
Corpus loaded: config/research_eval_benchmark_v0_corpus.json
  version=v0, entries=15, review_status=draft
Golden QA loaded: tests/fixtures/research_eval_benchmark/golden_qa_v0.json
  version=v0, pairs=10, review_status=reviewed
Dry-run complete. Inputs are valid.
```

### Full benchmark run

```bash
python -m polytool research-eval-benchmark \
  --corpus config/research_eval_benchmark_v0_corpus.json \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
  --output-dir artifacts/research/eval_benchmark
```

### Auto-discovery shorthand (v0 alias)

```bash
python -m polytool research-eval-benchmark --corpus v0 --golden-set v0
```

This auto-discovers:
- `config/research_eval_benchmark_v0_corpus.json` (falls back to `.draft.json`)
- `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` (falls back to `.draft.json`)

### Strict mode (refuse unreviewed QA)

```bash
python -m polytool research-eval-benchmark \
  --corpus v0 --golden-set v0 --strict
```

Returns exit code 1 if QA `review_status` is not `"reviewed"`.

### JSON stdout output

```bash
python -m polytool research-eval-benchmark \
  --corpus v0 --golden-set v0 --json
```

Appends a full JSON report to stdout after the human-readable summary.

---

## Step 4: Interpret the Recommendation

The recommendation label (A-E or NONE) is printed at the end:

```
Recommendation: [NONE] No action required
  No action threshold exceeded. System healthy.
```

Or if an action is needed:

```
Recommendation: [B] Old-paper re-ingest cleanup
  High fallback rate suggests re-ingest of abstract-only papers
  - Rule B: fallback_rate=52.0% > 40% — High fallback rate suggests re-ingest of abstract-only papers
```

### Recommendation thresholds

| Label | Trigger condition |
|-------|-------------------|
| A | `off_topic_rate_pct > 30%` |
| B | `fallback_rate_pct > 40%` |
| C | `p_at_5 < 0.5` |
| D | `>30%` of equation_heavy docs flagged not parseable |
| E | `median_chunks < 3` |

When multiple rules trigger, **A takes priority over B over C over D over E**.

---

## Step 5: Create the Baseline

Once the QA set has `review_status: "reviewed"` and the corpus is stable,
save the baseline:

```bash
python -m polytool research-eval-benchmark \
  --corpus config/research_eval_benchmark_v0_corpus.json \
  --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.json \
  --save-baseline \
  --output-dir artifacts/research/eval_benchmark
```

This writes `artifacts/research/eval_benchmark/baseline_v0.json`.

The baseline captures current metric values. Future runs can be compared
against it to detect regressions or improvements.

**Policy:** `--save-baseline` requires `review_status: "reviewed"` in the QA
set. The command will refuse and exit 1 if the QA is still in draft.

---

## Step 6: Re-run After Layer 1 Ships

Once Marker (Layer 1) has been deployed and papers are re-ingested with full
PDF parsing:

1. Re-run `research-acquire` for the corpus papers to re-ingest with updated
   body extraction
2. Re-run the benchmark:
   ```bash
   python -m polytool research-eval-benchmark --corpus v0 --golden-set v0
   ```
3. Compare metric 3 (fallback rate) and metric 9 (parser quality) to the baseline
4. If metric 3 improves below 40%, recommendation B should no longer trigger

---

## Output Files

Reports are written to `artifacts/research/eval_benchmark/` by default:

- `YYYY-MM-DD_benchmark_report.md` — Human-readable Markdown report
- `YYYY-MM-DD_benchmark_report.json` — Machine-readable JSON report
- `baseline_v0.json` — Frozen baseline (only written with `--save-baseline`)

---

## Troubleshooting

### "Corpus file not found"
Use `--corpus config/research_eval_benchmark_v0_corpus.json` (no `.draft.`) or
check that the file exists.

### Metrics 6 and 7 show "not_available"
The FTS5 lexical DB is not built. Run:
```bash
python -m polytool rag-refresh
```
Then re-run the benchmark.

### "strict mode requires reviewed QA"
Change `review_status` to `"reviewed"` in the golden QA file after operator
review, or omit `--strict`.

### Low P@5 (metric 6)
The expected_paper_id in QA pairs must exactly match the file_path or doc_id
stored in the lexical index. Check:
```bash
sqlite3 kb/rag/lexical/lexical.sqlite3 \
  "SELECT DISTINCT doc_id, file_path FROM chunks LIMIT 20"
```

### Low chunk counts (metric 5)
Check metadata_json for those documents:
```bash
sqlite3 kb/rag/knowledge/knowledge.sqlite3 \
  "SELECT id, title, chunk_count, metadata_json FROM source_documents WHERE chunk_count < 3"
```
