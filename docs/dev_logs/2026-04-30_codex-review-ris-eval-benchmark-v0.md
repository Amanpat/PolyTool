# Codex Review: RIS Eval Benchmark v0

**Date:** 2026-04-30
**Reviewer:** Codex
**Verdict:** PASS WITH FIXES
**Prompt B should proceed:** No. Hold Prompt B until the blocking metric/report fixes below are addressed and covered by targeted offline tests.

---

## Scope Reviewed

Reviewed the Scientific RAG Evaluation Benchmark v0 implementation from Claude Prompt A against the work packet and operator constraints.

Files reviewed:

- `git diff` - clean working tree, no unstaged implementation diff
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Scientific RAG Evaluation Benchmark.md`
- `tools/cli/research_eval_benchmark.py`
- `polytool/__main__.py`
- `packages/research/eval_benchmark/__init__.py`
- `packages/research/eval_benchmark/corpus.py`
- `packages/research/eval_benchmark/golden_qa.py`
- `packages/research/eval_benchmark/metrics.py`
- `packages/research/eval_benchmark/recommender.py`
- `packages/research/eval_benchmark/report.py`
- `tests/test_ris_eval_benchmark.py`
- `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json`
- `config/research_eval_benchmark_v0_corpus.draft.json`
- `docs/runbooks/research_eval_benchmark.md`
- `docs/dev_logs/2026-04-30_ris-eval-benchmark-v0-core.md`

Scope result:

- PASS: The commit only touched benchmark package, benchmark CLI, CLI registration, tests, config fixture, runbook, and dev log.
- PASS: No ingestion, parser production rollout, eval-provider, n8n, trading, execution, risk, or live-capital behavior was changed.
- PASS: No final golden QA file, final corpus file, or `baseline_v0.json` was created from draft QA.

---

## Commands Run

```powershell
git status --short
```

Output: no output; working tree was clean before review.

```powershell
git log --oneline -5
```

Output:

```text
a8b8664 feat(ris): Scientific RAG Evaluation Benchmark v0 core infrastructure
dbfb5b1 doc update
e226a14 Academic pipeline additions
bf1d80c docs(ris): Marker Layer 1 documentation close-out
4a409b8 fix(ris): Marker two-layer concurrency guard - _MARKER_DISABLED event stops zombie stacking
```

```powershell
python -m polytool --help
```

Output: exit 0. The global help loads and lists `research-eval-benchmark` under Research Intelligence.

```powershell
git diff
```

Output: no output.

```powershell
git show --stat --name-only --oneline HEAD
```

Output:

```text
a8b8664 feat(ris): Scientific RAG Evaluation Benchmark v0 core infrastructure
config/research_eval_benchmark_v0_corpus.draft.json
docs/dev_logs/2026-04-30_ris-eval-benchmark-v0-core.md
docs/runbooks/research_eval_benchmark.md
packages/research/eval_benchmark/__init__.py
packages/research/eval_benchmark/corpus.py
packages/research/eval_benchmark/golden_qa.py
packages/research/eval_benchmark/metrics.py
packages/research/eval_benchmark/recommender.py
packages/research/eval_benchmark/report.py
polytool/__main__.py
tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json
tests/test_ris_eval_benchmark.py
tools/cli/research_eval_benchmark.py
```

```powershell
rg --files packages/research/eval_benchmark
rg --files tests/fixtures/research_eval_benchmark
rg --files config | rg 'research_eval_benchmark'
rg --files docs/dev_logs | rg 'ris-eval-benchmark'
```

Output: each `rg.exe` invocation failed with `Access is denied`; review continued with PowerShell `Get-ChildItem` and direct file reads.

```powershell
python -m pytest tests/test_ris_eval_benchmark.py
```

Output:

```text
collected 45 items
45 passed in 0.25s
```

```powershell
python -m polytool research-eval-benchmark --help
```

Output: exit 0. The command exposes `--corpus`, `--golden-set`, `--output-dir`, `--db`, `--lexical-db`, `--dry-run`, `--strict`, `--save-baseline`, and `--json`.

```powershell
python -m polytool research-eval-benchmark --corpus v0 --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json --dry-run
```

Output:

```text
Corpus loaded: D:\Coding Projects\Polymarket\PolyTool\config\research_eval_benchmark_v0_corpus.draft.json
  version=v0, entries=1, review_status=draft
Golden QA loaded: tests\fixtures\research_eval_benchmark\golden_qa_v0.draft.json
  version=v0, pairs=5, review_status=operator_review_required
Dry-run complete. Inputs are valid.
WARNING: QA set is NOT operator-reviewed (review_status='operator_review_required'). Results are indicative only.
```

```powershell
python -m polytool research-eval-benchmark --corpus v0 --golden-set tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json --save-baseline --dry-run
```

Output:

```text
WARNING: QA set is NOT operator-reviewed (review_status='operator_review_required'). Results are indicative only.
ERROR: --save-baseline requires reviewed QA. Operator must review the QA set and set review_status='reviewed'.
```

Exit code: 1.

```powershell
Test-Path -LiteralPath 'artifacts/research/eval_benchmark/baseline_v0.json'
```

Output:

```text
False
```

---

## Findings By Severity

### Blocking

1. Metric 6 can mark answer correctness from the wrong document.

Evidence: `packages/research/eval_benchmark/metrics.py:374-383` sets `answer_found=True` if `expected_answer_substring` appears in any top-5 chunk, independent of whether that chunk belongs to `expected_paper_id`. This can overstate answer correctness when the phrase is common across papers.

Exact fix:

- In `compute_metric_6_retrieval_answer_quality()`, only count `answer_found=True` for a result that also matches the expected paper.
- Add per-question detail fields: `matched_doc_id`, `matched_file_path`, `matched_rank`, `answer_match_rank`, and `top_5_doc_ids`.
- Add an offline test where the expected answer substring appears only in a non-expected document; expected `answer_correctness_rate` must be `0.0`.

2. Metric 7 does not measure the packet's citation/source traceability requirement.

Evidence: `packages/research/eval_benchmark/metrics.py:453-500` only checks whether a retrieved chunk doc id maps back to a known source document or URL. It does not verify source PDF/file path availability, page number if available, or exact passage reconstruction in cached body. It also emits no supporting per-question detail.

Exact fix:

- Update `compute_metric_7_citation_traceability()` so a traceable result requires the expected paper hit plus reconstructable source reference: source URL or file path, page/page label when present, and retrieved snippet or chunk text containing the expected answer substring.
- Emit numeric subcounts: `traceable_count`, `evaluated_count`, `missing_source_count`, `missing_page_count`, `missing_passage_count`, and `traceability_rate_pct`.
- Emit detail rows per evaluated QA pair with the missing reason.
- Add offline tests for a fully traceable row and for missing page/source/passage failures.

3. Metric 9 does not provide the required parser-quality issue counts and ignores its sampling filter.

Evidence: `packages/research/eval_benchmark/metrics.py:565-639` accepts `sampled_categories` but never uses it to filter. It samples every non-abstract document and only reports `sampled_count`, `equation_heavy_count`, and `table_heavy_count`; the packet requires counts of papers with equation, table, and section issues.

Exact fix:

- Filter samples to manifest-tagged parser-quality categories, at minimum `equation_heavy` and `table_heavy`.
- Report deterministic numeric issue counts and rates: `equation_not_parseable_count`, `table_not_detectable_count`, `section_headers_missing_count`, `missing_page_count`, plus rates over the relevant sample denominator.
- Include `skipped_abstract_fallback_count` if abstracts are intentionally excluded.
- Add tests proving prose/outlier records are excluded from the parser-quality sample and that each issue count increments.

4. Reports omit the rule audit trail even though the recommender computes it.

Evidence: `packages/research/eval_benchmark/recommender.py:47-145` records `triggered_rules`, but `packages/research/eval_benchmark/report.py:111-219` only accepts and writes recommendation label plus justification. The Markdown/JSON artifacts lose the exact threshold rules that fired, making the A-E recommendation less auditable after stdout is gone.

Exact fix:

- Change report generation to accept either the full `RecommendationResult` or an explicit `triggered_rules` list.
- Include `triggered_rules` in JSON under `recommendation`.
- Include a Markdown subsection listing each fired rule and state "No threshold rules fired" when empty.
- Add report tests asserting triggered rules are preserved.

### Major

5. Metric 1 checks title only, not title plus abstract as specified.

Evidence: `packages/research/eval_benchmark/metrics.py:119-137` lowercases `doc["title"]` and checks only that string. The work packet specifies title and abstract keyword overlap.

Exact fix:

- Include abstract/body excerpt text from metadata fields such as `_meta.abstract`, `_meta.body`, or an explicit selected abstract field if the KnowledgeStore has one.
- Validate `seed_topic_keywords` as a non-empty list of non-empty strings.
- Add a test where the title is generic but the abstract contains a seed keyword; expected off-topic count must be zero.

6. Metric 8 omits canonical-id duplicates and similar-body/title duplicates.

Evidence: `packages/research/eval_benchmark/metrics.py:522-550` groups exact `content_hash` and exact normalized title only. The packet requires duplicates by identical content hash, identical canonical ids, and identical title with similar body.

Exact fix:

- Extract canonical ids from metadata (`canonical_id`, `canonical_ids`, DOI/arXiv id aliases if present) and group duplicates by each canonical id.
- Add a deterministic body-similarity check for exact normalized title plus similar body, using a simple local heuristic such as normalized body hash prefix, token Jaccard over body excerpts, or an existing repo helper if available.
- Report `canonical_id_dupes` and `similar_title_body_dupes`, with detail rows.
- Add offline tests for canonical-id and similar-body duplicates.

7. Metric 5 omits the review-priority flag required for low-chunk suspicious records.

Evidence: `packages/research/eval_benchmark/metrics.py:283-304` lists source id, title, chunk count, body length, and body source, but does not emit a `review_priority` field.

Exact fix:

- Add deterministic `review_priority`, for example `high` for zero chunks, abstract fallback, or very short body, `medium` for 1-2 chunks with PDF body, and `low` otherwise.
- Add tests for the priority mapping.

8. Missing corpus rows are silently dropped from the benchmark population.

Evidence: `packages/research/eval_benchmark/metrics.py:55-87` loads only rows found in `source_documents`, and `compute_all_metrics()` reports `corpus_size=len(docs)` at `metrics.py:705`. If the manifest contains missing or placeholder source ids, a full run can produce a zero-document report instead of clearly failing or warning.

Exact fix:

- Compare manifest source ids to loaded document ids in `compute_all_metrics()`.
- Either fail full benchmark runs when any manifest source id is missing, or add a first-class warning/error metric with `manifest_entries`, `loaded_docs`, `missing_source_ids`, and `missing_count`.
- At minimum, make `--strict` fail when corpus rows are missing.
- Add a test where one manifest id is absent from the DB.

### Non-blocking

9. The draft fixture count is intentionally below the packet's final QA target.

Evidence: `tests/fixtures/research_eval_benchmark/golden_qa_v0.draft.json` contains five draft QA pairs, while the packet calls for 30-50 final operator-reviewed QA pairs. This is acceptable for a draft scaffold, but the runbook should keep making clear that `golden_qa_v0.json` is not present and must be operator-reviewed before baseline.

Exact fix:

- No implementation fix required before Prompt B.
- When the operator creates final QA, enforce the final target count in review or strict mode if desired.

---

## Check Matrix

1. Scope: PASS. No prohibited ingestion/parser/eval-provider/n8n/trading behavior changed.
2. CLI: PASS. Command is registered in `polytool/__main__.py`, loads via lazy entrypoint, and help exits 0.
3. Metrics: PASS WITH FIXES. All nine metric objects exist, but metrics 6, 7, 8, and 9 do not fully measure the packet definitions yet.
4. Determinism: PASS WITH FIXES. Exact-match is used and no LLM calls exist; fix metric 6 matching semantics so deterministic values are also correct.
5. QA safety: PASS. Draft QA cannot create `baseline_v0.json`; `--save-baseline` requires `review_status="reviewed"`.
6. Corpus: PASS WITH FIXES. Manifest is versioned and clear, but missing source ids are silently dropped during metric computation.
7. Reports: PASS WITH FIXES. Markdown and JSON outputs exist, but recommendation triggered rules are not persisted.
8. Recommendation: PASS WITH FIXES. Rule-based A-E logic is auditable in code and documented in the runbook, but the report artifacts omit the triggered rule audit trail.
9. Tests: PASS WITH FIXES. Targeted tests are offline and pass, but they currently encode the incomplete metric behavior above.
10. Docs: PASS. Runbook covers corpus population, QA review, dry-run/full run, baseline creation, and interpretation.

---

## Decisions Made During Review

- No implementation code was changed. This review only adds the requested dev log.
- Verdict is `PASS WITH FIXES` instead of `FAIL` because the implementation is correctly scoped, wired, tested, and baseline-safe; the remaining issues are targeted metric/report correctness fixes rather than a full rewrite.
- Prompt B should not proceed yet because the benchmark can currently produce misleading retrieval, citation, duplicate, and parser-quality signals.

---

## Open Questions / Blockers

- Which exact KnowledgeStore metadata fields should be treated as canonical abstract/body/page fields for metrics 1, 7, and 9? The current code uses `_meta` opportunistically; the targeted patch should confirm actual stored metadata from a real Layer 0 row before finalizing field names.
- Should full benchmark runs fail on missing corpus source ids, or merely warn and expose `missing_source_ids` in JSON? For a baseline candidate, failing is safer.

---

## Codex Review Summary

Review tier: adversarial review requested by operator for benchmark correctness.

Issues found:

- 4 blocking
- 4 major
- 1 non-blocking

Issues addressed in this work unit:

- Review log created.
- No implementation fixes applied.
