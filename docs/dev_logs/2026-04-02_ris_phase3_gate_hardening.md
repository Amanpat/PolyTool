# Dev Log: RIS Phase 3 — Evaluation Gate Hardening

**Date:** 2026-04-02
**Plan ref:** quick-260402-m6t
**Branch:** feat/ws-clob-feed (worktree-agent-afba9780)

---

## Objective

Add deterministic signal extraction before LLM scoring in the RIS evaluation
gate, without replacing LLM scoring. Introduce near-duplicate detection, structured
artifact persistence, and richer calibration analytics.

---

## Files Changed

| File | Action | Rationale |
|------|--------|-----------|
| `packages/research/evaluation/feature_extraction.py` | Created | Per-family feature extractors (academic/github/blog/news/forum_social/default) |
| `packages/research/evaluation/dedup.py` | Created | Content-hash + shingle near-dup detection |
| `packages/research/evaluation/artifacts.py` | Created | JSONL artifact persistence for eval runs |
| `packages/research/evaluation/types.py` | Modified | Added SOURCE_FAMILY_OFFSETS hook |
| `packages/research/evaluation/__init__.py` | Modified | Updated exports for new public symbols |
| `packages/research/evaluation/evaluator.py` | Modified | Phase 3 pipeline: dedup + features + artifact wired in |
| `packages/research/synthesis/calibration.py` | Modified | compute_eval_artifact_summary(), format_calibration_report() extended |
| `tools/cli/research_eval.py` | Modified | --artifacts-dir flag; features+near_duplicate in JSON output |
| `tests/test_ris_phase3_features.py` | Created | 47 new tests (all passing) |
| `docs/features/FEATURE-ris-phase3-gate-hardening.md` | Created | Feature documentation |
| `docs/CURRENT_STATE.md` | Modified | RIS Phase 3 shipped entry |

---

## Structured Features Added by Family

### academic (arxiv, ssrn, book)
- `has_doi`: regex `10.\d{4,}/\S+`
- `has_arxiv_id`: regex `arxiv:\d{4}.\d{4,5}` (case-insensitive)
- `has_ssrn_id`: regex `ssrn:\d{6,}` (case-insensitive)
- `methodology_cues`: count of keywords in `["regression", "p-value", "sample size", "dataset", "experiment", "methodology", "control group", "confidence interval", "hypothesis test"]`
- `has_known_author`: author not in {unknown, "", none}
- `has_publish_date`: source_publish_date is set

### github (github)
- `stars`: from metadata dict
- `forks`: from metadata dict
- `has_readme_mention`: "readme" in body
- `has_license_mention`: "license" in body
- `commit_recency`: from metadata dict

### blog / news
- `has_byline`: regex for "By Name" / "written by Name" / "author: Name"
- `has_date`: source_publish_date set OR date-like pattern in body
- `heading_count`: count of markdown `# headings`
- `paragraph_count`: count of double-newline paragraph breaks
- `has_blockquote`: presence of markdown `>` blockquote

### forum_social (reddit, twitter, youtube)
- `has_screenshot`: "screenshot" / "image" / "img" / "photo" / "pic" in body
- `has_data_mention`: "data" / "chart" / "graph" / "table" / "figure" in body
- `reply_count`: from metadata dict
- `specificity_markers`: count of percentage patterns + dollar patterns

### manual / default
- `body_length`: len(body)
- `word_count`: len(body.split())
- `has_url`: "http://" or "https://" in body

---

## New Calibration Signals Exposed

From `compute_eval_artifact_summary()`:

- `gate_distribution`: ACCEPT/REVIEW/REJECT counts and percentages
- `hard_stop_distribution`: count per stop_type (e.g., too_short=5, spam_malformed=2)
- `family_gate_distribution`: per-family ACCEPT/REVIEW/REJECT (e.g., academic: ACCEPT=12, REJECT=2)
- `dedup_stats`: exact_duplicates, near_duplicates, unique counts
- `avg_features_by_family`: numeric feature averages by family

These appear in the calibration report when `format_calibration_report()` is called
with `eval_artifacts_summary=...`.

---

## Commands Run and Results

### Targeted feature extraction, dedup, artifact tests (Task 1 TDD)

```
rtk python -m pytest tests/test_ris_phase3_features.py::TestAcademicFeatures \
  tests/test_ris_phase3_features.py::TestGithubFeatures \
  tests/test_ris_phase3_features.py::TestBlogNewsFeatures \
  tests/test_ris_phase3_features.py::TestForumSocialFeatures \
  tests/test_ris_phase3_features.py::TestDefaultFeatures \
  tests/test_ris_phase3_features.py::TestDedup \
  tests/test_ris_phase3_features.py::TestArtifactPersistence \
  tests/test_ris_phase3_features.py::TestSourceFamilyOffsets -v --tb=short
```
Result: **38 passed**

### Integration tests + existing evaluation and calibration tests (Task 2)

```
rtk python -m pytest tests/test_ris_phase3_features.py tests/test_ris_evaluation.py tests/test_ris_calibration.py -v --tb=short
```
Result: **115 passed**

### Full regression suite (Task 3)

```
rtk python -m pytest tests/ -q --tb=short
```
Result: **3111 passed, 4 failed** (all 4 failures pre-existing: require local dossier
artifacts under `artifacts/dossiers/users/drpufferfish/` which are gitignored runtime
files, not present in worktree; completely unrelated to Phase 3 changes)

Zero new failures introduced by Phase 3 changes.

### CLI smoke test

```
python -m polytool --help
```
Result: CLI loads cleanly, no import errors.

---

## Deviations from Plan

**None.** All tasks executed as specified.

Minor adjustment: `test_evaluator_near_duplicate_rejected` required a longer test
body than originally written (single-word change in a short body produced Jaccard
0.82, below the 0.85 threshold). Fixed by using a ~100-word body where the last
word changes — Jaccard 0.895 > 0.85. This is correct behavior, not a bug.

---

## Next-Step Recommendation

Stay prompt-guided for 1-2 more phases. The SOURCE_FAMILY_OFFSETS hook and
per-family calibration artifact data are the prerequisites for config-driven weighting.

**Trigger for next action:** When `eval_artifacts.jsonl` has >= 50 entries across
>= 3 source families:

1. Load artifacts with `load_eval_artifacts()`
2. Call `compute_eval_artifact_summary()` to inspect family-level gate distributions
3. If a family shows consistently elevated REJECT rates vs. others with similar
   content quality, derive initial offset values
4. Populate SOURCE_FAMILY_OFFSETS in `types.py` with conservative adjustments
   (e.g., +1 credibility for academic, -1 for forum_social)
5. Write tests for offset application before wiring into evaluator

Until then, the LLM rubric and SOURCE_FAMILY_GUIDANCE strings carry all
family-specific signal. Do not pre-populate offsets without data.

---

## Codex Review

Tier: Skip (docs, tests, regex-only evaluation helpers — no execution/order/signing logic).
EOF
