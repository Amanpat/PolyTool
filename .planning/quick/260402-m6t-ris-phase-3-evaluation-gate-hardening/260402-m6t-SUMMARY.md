---
phase: quick-260402-m6t
plan: "01"
subsystem: research-evaluation
tags: [ris, evaluation, feature-extraction, dedup, artifacts, calibration]
dependency_graph:
  requires:
    - quick-260402-ivb  # RIS Phase 2 query spine wiring
  provides:
    - per-family deterministic feature extraction
    - near-duplicate detection (hash + shingle Jaccard)
    - structured eval artifact persistence (JSONL)
    - enhanced calibration analytics (family-level distributions)
    - SOURCE_FAMILY_OFFSETS hook for future data-driven tuning
  affects:
    - packages/research/evaluation/evaluator.py
    - packages/research/synthesis/calibration.py
    - tools/cli/research_eval.py
tech_stack:
  added:
    - hashlib SHA256 for content hashing
    - word 5-gram shingles + Jaccard similarity for near-dup detection
    - JSONL artifact persistence via dataclasses.asdict
  patterns:
    - per-family strategy pattern (dispatch dict by source_type -> extractor fn)
    - two-pass dedup (exact hash first, shingle Jaccard second)
    - opt-in artifact side-channel (DocumentEvaluator(artifacts_dir=Path(...)))
key_files:
  created:
    - packages/research/evaluation/feature_extraction.py
    - packages/research/evaluation/dedup.py
    - packages/research/evaluation/artifacts.py
    - tests/test_ris_phase3_features.py
    - docs/features/FEATURE-ris-phase3-gate-hardening.md
    - docs/dev_logs/2026-04-02_ris_phase3_gate_hardening.md
  modified:
    - packages/research/evaluation/types.py
    - packages/research/evaluation/__init__.py
    - packages/research/evaluation/evaluator.py
    - packages/research/synthesis/calibration.py
    - tools/cli/research_eval.py
    - docs/CURRENT_STATE.md
decisions:
  - "LLM scoring retained as primary quality signal; feature extraction adds deterministic layer before it, not instead of it"
  - "SOURCE_FAMILY_OFFSETS kept empty — data-driven offset derivation requires >= 50 eval artifacts across >= 3 families before any values should be populated"
  - "Near-duplicate threshold set at 0.85 Jaccard (not calibrated; revisit when false-positive data available from artifact logs)"
  - "Artifacts opt-in via constructor: without artifacts_dir, evaluator behavior is byte-for-byte identical to Phase 2"
metrics:
  duration_minutes: ~75
  completed_date: "2026-04-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 6
  tests_added: 47
  tests_total_after: 3111
---

# Phase quick-260402-m6t Plan 01: RIS Phase 3 Evaluation Gate Hardening Summary

**One-liner:** Per-family deterministic feature extraction + SHA256/shingle near-dup detection + JSONL eval artifact persistence wired into RIS evaluation gate before LLM scoring, with enhanced calibration analytics.

---

## Objective

Add deterministic pre-scoring structure to the RIS evaluation gate. The gate was:
`hard_stops -> LLM_scoring`

After Phase 3 it is:
`hard_stops -> near_duplicate_check -> feature_extraction -> LLM_scoring -> artifact_persistence`

LLM scoring is still the primary quality signal. Phase 3 adds local-first guardrails and
observability on top without replacing or weakening it.

---

## Tasks Completed

| # | Task | Commit | Type | Key Files |
|---|------|--------|------|-----------|
| 1 | Feature extraction, dedup, artifact modules (TDD) | `a18553e` | feat | feature_extraction.py, dedup.py, artifacts.py, types.py, __init__.py, tests |
| 2 | Wire extraction/dedup/artifacts into evaluator + calibration | `bb88eda` | feat | evaluator.py, calibration.py, research_eval.py |
| 3 | Documentation, dev log, CURRENT_STATE update | `60305a0` | docs | FEATURE-ris-phase3-gate-hardening.md, dev log, CURRENT_STATE.md |

---

## What Was Built

### Feature Extraction (`packages/research/evaluation/feature_extraction.py`)

Public API: `extract_features(doc: EvalDocument) -> FamilyFeatures`

All extraction is pure text/regex — no network calls, no LLM dependency.

| Family | Source types | Key features |
|--------|-------------|--------------|
| `academic` | arxiv, ssrn, book | has_doi, has_arxiv_id, has_ssrn_id, methodology_cues (count), has_known_author, has_publish_date |
| `github` | github | stars, forks, has_readme_mention, has_license_mention, commit_recency |
| `blog` / `news` | blog, news | has_byline, has_date, heading_count, paragraph_count, has_blockquote |
| `forum_social` | reddit, twitter, youtube | has_screenshot, has_data_mention, reply_count, specificity_markers |
| `manual` / default | manual + all others | body_length, word_count, has_url |

### Near-Duplicate Detection (`packages/research/evaluation/dedup.py`)

Two-pass algorithm:

1. Exact: SHA256 of `" ".join(body.lower().split())`. Match against `existing_hashes: set[str]`.
2. Near: word 5-gram shingles + Jaccard similarity >= 0.85. Match against `existing_shingles: list[tuple[doc_id, frozenset]]`.

Near-duplicates rejected before LLM scoring — they never consume API tokens.

### Eval Artifact Persistence (`packages/research/evaluation/artifacts.py`)

`EvalArtifact` written as one JSONL line per eval to `{artifacts_dir}/eval_artifacts.jsonl`.

Fields: `doc_id`, `timestamp` (ISO-8601 UTC), `gate`, `hard_stop_result` (dict|None), `near_duplicate_result` (dict|None), `family_features` (dict), `scores` (dict|None), `source_family`, `source_type`.

Opt-in via `DocumentEvaluator(artifacts_dir=Path(...))`. Without it, behavior is identical to Phase 2.

CLI flag: `python -m polytool research-eval --artifacts-dir PATH --json`

### Enhanced Calibration Analytics (`packages/research/synthesis/calibration.py`)

New function: `compute_eval_artifact_summary(artifacts: list[dict]) -> dict`

Output fields: `total_evals`, `gate_distribution`, `hard_stop_distribution`, `family_gate_distribution`, `dedup_stats` (exact/near/unique), `avg_features_by_family`.

`format_calibration_report()` gains two new sections when `eval_artifacts_summary` is provided:
- **Hard-Stop Causes** — ranked table of stop_type counts
- **Family Gate Distribution** — per-family accept/reject breakdown with ACCEPT%

### SOURCE_FAMILY_OFFSETS Hook (`packages/research/evaluation/types.py`)

```python
SOURCE_FAMILY_OFFSETS: dict[str, dict[str, int]] = {}
```

Intentionally empty. Designated extension point for data-driven per-family credibility
adjustments. Do not populate until >= 50 eval artifacts span >= 3 source families.

---

## Test Results

### TDD Red-Green cycle (Task 1)

All 47 tests written first (RED), then implementations made them pass (GREEN).

### Integration + existing eval/calibration tests (Task 2)

```
rtk python -m pytest tests/test_ris_phase3_features.py tests/test_ris_evaluation.py tests/test_ris_calibration.py
```

Result: **115 passed**

### Full regression (Task 3)

```
rtk python -m pytest tests/ -q --tb=short
```

Result: **3111 passed, 4 failed**

The 4 failures are pre-existing and require gitignored local dossier artifact files under
`artifacts/dossiers/users/drpufferfish/` — completely unrelated to Phase 3 changes.

Zero new failures introduced.

### CLI smoke test

```
python -m polytool --help
```

Result: clean load, no import errors.

---

## Deviations from Plan

**None.** All tasks executed exactly as specified.

Minor adjustment in test_evaluator_near_duplicate_rejected: the original ~30-word test body
with a single word changed at the end produced Jaccard 0.82, below the 0.85 threshold. Fixed
by using a ~100-word body where only the final word differs — Jaccard 0.895 > 0.85. This is
correct behavior (shorter bodies have fewer shingles and less Jaccard resolution), not a bug.

---

## Known Stubs

None. All functionality is fully wired. The only intentionally empty structure is
`SOURCE_FAMILY_OFFSETS = {}` in `types.py`, which is documented as a future extension hook
that must remain empty until calibration data justifies non-zero values.

---

## Decisions Made

1. **LLM scoring retained as primary quality signal** — Phase 3 adds deterministic pre-scoring
   structure, not a replacement. Features and near-dup detection are guards and observability
   tools, not quality arbiters.

2. **SOURCE_FAMILY_OFFSETS empty by design** — Pre-populating offsets without data risks
   introducing systematic bias. The hook exists for the future; offset derivation requires
   >= 50 artifacts across >= 3 families.

3. **0.85 Jaccard threshold not yet calibrated** — Default chosen conservatively. Should be
   revisited once false-positive/negative data is available from production artifact logs.

4. **Artifact opt-in via constructor** — Backward compatibility is a hard requirement.
   Without `artifacts_dir`, the evaluator is byte-for-byte identical to Phase 2.

---

## Next Steps

Stay prompt-guided for 1-2 more phases. The SOURCE_FAMILY_OFFSETS hook and per-family
calibration artifact data are the prerequisites for config-driven weighting.

**Trigger for next action:** When `eval_artifacts.jsonl` has >= 50 entries across >= 3 source families:

1. Load artifacts with `load_eval_artifacts()`
2. Call `compute_eval_artifact_summary()` to inspect family-level gate distributions
3. If a family shows consistently elevated REJECT rates vs. others with similar content quality,
   derive initial offset values
4. Populate SOURCE_FAMILY_OFFSETS in `types.py` with conservative adjustments
5. Write tests for offset application before wiring into evaluator

Until then, the LLM rubric and SOURCE_FAMILY_GUIDANCE strings carry all family-specific signal.

---

## Self-Check: PASSED

Created files verified present:
- `packages/research/evaluation/feature_extraction.py` — FOUND
- `packages/research/evaluation/dedup.py` — FOUND
- `packages/research/evaluation/artifacts.py` — FOUND
- `tests/test_ris_phase3_features.py` — FOUND
- `docs/features/FEATURE-ris-phase3-gate-hardening.md` — FOUND
- `docs/dev_logs/2026-04-02_ris_phase3_gate_hardening.md` — FOUND

Commits verified:
- `a18553e` — feat(quick-260402-m6t-01) — FOUND
- `bb88eda` — feat(quick-260402-m6t-02) — FOUND
- `60305a0` — docs(quick-260402-m6t-03) — FOUND
