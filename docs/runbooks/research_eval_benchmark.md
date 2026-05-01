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
- Academic body text has been cached (populated by `research-acquire`):
  `artifacts/research/raw_source_cache/academic/*.json`
- The FTS5 lexical index is built for the corpus papers (see Step 2.5):
  `kb/rag/lexical/lexical.sqlite3`
  (metrics 6 and 7 show as `not_available` without it)
- Python environment: `python -m polytool --help` succeeds without import errors

> **Do NOT run `python -m polytool rag-refresh`** to build the lexical index for
> the benchmark. That command scans all `kb/` and `artifacts/` directories (slow,
> unscoped). Use the dedicated scoped refresh command in Step 2.5 instead.

---

## Step 1: Discover and Populate the Corpus Manifest

### Discover what's in the KnowledgeStore

```bash
# List all academic records with chunk_count, body_source, and body_length:
python -m polytool research-eval-benchmark --discover-corpus
```

This prints a human-readable table plus a JSON array of candidate records.
Pipe to a file to use as input when editing the manifest:

```bash
python -m polytool research-eval-benchmark --discover-corpus > /tmp/candidates.txt
```

### Promote the draft manifest

The draft manifest at `config/research_eval_benchmark_v0_corpus.draft.json`
was populated with 23 real academic records (as of 2026-04-30) from the
KnowledgeStore. It is ready to use for draft runs.

To create the final manifest for baseline creation:

1. Copy the draft:
   ```bash
   cp config/research_eval_benchmark_v0_corpus.draft.json \
      config/research_eval_benchmark_v0_corpus.json
   ```
2. Review each entry's `category` against the paper's actual content:
   - `equation_heavy` — math-formula-dense papers (Avellaneda-Stoikov, etc.)
   - `table_heavy` — data-table-dense papers
   - `prose_heavy` — narrative/survey papers
   - `outlier` — included intentionally to test off-topic detection; remove
     if these papers shouldn't be in the corpus
   - `null` — uncategorised; assessed by metrics but excluded from metric 9
3. Remove any `"off-topic-for-metric-1-test"` tag entries if they are truly
   off-topic (they were included in the draft to validate metric 1)
4. Add any new papers ingested since 2026-04-30 using `--discover-corpus`

### Category reference

| Category | Use for |
|----------|---------|
| `equation_heavy` | Papers with dense formulas (assessed by metric 9) |
| `table_heavy` | Papers with data tables (assessed by metric 9) |
| `prose_heavy` | Narrative/survey papers (not assessed by metric 9) |
| `outlier` | Intentionally off-topic entries for metric 1 validation |
| `null` | Uncategorised — counted in all metrics except metric 9 |

Aim for 30-50 papers. The current Layer 0 store has 39 academic records;
23 were selected for the draft corpus (17 high-quality, 3 outlier, 3 low-chunk).

---

## Step 2: Create and Review the Golden QA Set

The draft QA set lives at:
`tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`

**Current state (2026-04-30):** 5 placeholder QA pairs exist. All
`expected_paper_id` values are `"REPLACE_WITH_DOC_ID_OR_FILE_PATH"`. No
final `golden_qa_v0.json` exists yet. This is the operator's review step
before baseline creation.

**Target:** 30-50 reviewed QA pairs for meaningful P@5 and answer quality scores.

To create the reviewed QA set:

1. Copy the draft:
   ```bash
   cp tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json \
      tests/fixtures/research_eval_benchmark/golden_qa_v0.json
   ```
2. For each QA pair, replace `"REPLACE_WITH_DOC_ID_OR_FILE_PATH"` with the
   real document ID (SHA-256 string) of the paper that answers the question.
   Verify the ID against `--discover-corpus` or the KnowledgeStore directly.
3. Verify `expected_answer_substring` actually appears verbatim in the paper's
   stored body text. Query the chunk store to confirm:
   ```bash
   sqlite3 kb/rag/lexical/lexical.sqlite3 \
     "SELECT chunk_text FROM chunks WHERE doc_id = '<REAL_ID>' LIMIT 5"
   ```
4. Edit `expected_section_or_page` to the correct section/page where applicable.
5. Add more QA pairs (aim for 30 minimum). Each must cover a different paper
   from the corpus to get meaningful P@5 coverage.
6. When all pairs are verified, change:
   ```json
   "review_status": "operator_review_required"
   ```
   to:
   ```json
   "review_status": "reviewed"
   ```

**CRITICAL:** Do not change `review_status` to `"reviewed"` before all
`expected_paper_id` values are replaced and all `expected_answer_substring`
values are confirmed against real body text. The baseline depends on this
being accurate.

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

## Step 2.5: Build the Scoped Lexical Index (Required for Metrics 6 and 7)

Metrics 6 (Retrieval P@5) and 7 (Citation Traceability) require the FTS5 lexical
index to contain chunks for the corpus papers. Use the **scoped refresh command**
— it indexes only the 23 corpus papers from the raw source cache in under 10 seconds:

```bash
python -m polytool research-eval-benchmark --corpus v0 --refresh-lexical
```

Expected output:
```
[refresh-lexical] corpus entries: 23
[refresh-lexical] cache_dir: .../artifacts/research/raw_source_cache/academic
[refresh-lexical] lexical_db: .../kb/rag/lexical/lexical.sqlite3
[refresh-lexical] resolved 23/23 URLs from KnowledgeStore
[refresh-lexical] found 22 bodies in cache_dir
  [indexed]      b1982ae05e5cd305...  chunks=33
  ...
[refresh-lexical] done — indexed=22, skipped=1 (...), total_chunks=567, elapsed=3.7s
```

The 1 skipped paper (`d744370b...` — Prediction Market Microstructure stub) has no
body text in the raw source cache. This is expected for low-chunk stub entries.

### What the scoped refresh does

- Loads the 23 corpus source_ids from the corpus manifest.
- Looks up each paper's `source_url` in `kb/rag/knowledge/knowledge.sqlite3`.
- Matches the URL to a raw cache file in `artifacts/research/raw_source_cache/academic/`.
- Reads `payload.body_text` from the cache file (the full extracted PDF body).
- Chunks the body text (400 words, 80-word overlap — same as rag-refresh defaults).
- Inserts chunks into `kb/rag/lexical/lexical.sqlite3` with:
  - `doc_id = source_id` (matches `expected_paper_id` in QA pairs)
  - `file_path = source_id` (same, for metric 6 paper matching)
  - `doc_type = "academic"`
- Operation is **idempotent** — safe to re-run; stale chunks are replaced.

### Using a custom corpus path or DB

```bash
# Explicit corpus path
python -m polytool research-eval-benchmark \
  --corpus config/research_eval_benchmark_v0_corpus.draft.json \
  --refresh-lexical

# Non-default lexical DB or raw cache dir
python -m polytool research-eval-benchmark \
  --corpus v0 \
  --refresh-lexical \
  --lexical-db /path/to/custom/lexical.sqlite3 \
  --raw-cache /path/to/cache/dir
```

### Note on Metric 6 retrieval search

Metrics 6 and 7 search the lexical index using each QA pair's
`expected_answer_substring` (the key claim text from the paper), not the full
question. This is because BM25 AND-matching on long question sentences rarely
finds a match in any single chunk. Searching for the answer substring directly
tests whether the expected content is indexed and retrievable — a valid
"oracle retrieval" test for corpus quality.

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

- `YYYY-MM-DD_benchmark_report_draft.md` — Markdown report from unreviewed QA run
- `YYYY-MM-DD_benchmark_report_draft.json` — JSON report from unreviewed QA run
- `YYYY-MM-DD_benchmark_report.md` — Markdown report from reviewed-QA run
- `YYYY-MM-DD_benchmark_report.json` — JSON report from reviewed-QA run
- `baseline_v0.json` — Frozen baseline (only written with `--save-baseline`; requires reviewed QA)

The `_draft` suffix is appended automatically when `review_status != "reviewed"`.

---

## Troubleshooting

### "Corpus file not found"
Use `--corpus config/research_eval_benchmark_v0_corpus.json` (no `.draft.`) or
check that the file exists.

### Metrics 6 and 7 show "not_available"
The FTS5 lexical DB is not built or has no academic chunks. Run the scoped refresh:
```bash
python -m polytool research-eval-benchmark --corpus v0 --refresh-lexical
```
Do NOT use `python -m polytool rag-refresh` — it scans all directories and is
too broad/slow for this use case. Re-run the benchmark after the scoped refresh.

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
