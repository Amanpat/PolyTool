---
title: L3 V1 Svm Default Off Integration
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3 v1 SVM Default-Off Integration

**Date:** 2026-05-06
**Feature:** Feature 3 — RIS L3 v1 SVM Topic Filter Readiness + Training
**Scope:** CLI/default-off integration only. Lexical v1.1 remains default. SVM enforce is blocked.

---

## Goal

Wire the trained SVM runtime scorer (`SvmRelevanceScorer`) behind explicit CLI flags so
operators can run dry-run / hold-review evidence collection without disturbing the existing
lexical default. Enforce mode for SVM is blocked until the label corpus reaches >=150 and
Director gives approval.

---

## Files Changed

### `packages/research/relevance_filter/scorer.py`

Already updated by Prompt A (committed). `FilterDecision` already has the required SVM
audit fields: `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`,
`svm_lexical_baseline_note`. No further change needed.

### `tools/cli/research_acquire.py`

Three new optional arguments added:

- `--prefetch-filter-scorer {lexical,svm}` — default `lexical`
- `--prefetch-svm-model PATH` — required when scorer=svm and mode is not off
- `--prefetch-svm-metadata PATH` — optional; inferred from model path when omitted

Two validation checks added (before URL/search validation so errors fire early):

- `scorer=svm + mode=enforce` → rc=1 with message:
  `"Error: SVM enforce is blocked until >=150 labels and Director approval. Use dry-run or hold-review."`
- `scorer=svm + mode!=off + no model path` → rc=1 with message:
  `"Error: --prefetch-svm-model PATH is required ..."`

`_score_candidate_for_filter` updated to dispatch by scorer type:

- `scorer_type == "svm"` → imports `SvmRelevanceScorer`, `SvmRuntimeConfig`; constructs
  scorer with `model_path` and optional `metadata_path`; calls `scorer.score(candidate)`
- `scorer_type == "lexical"` (default) → existing path unchanged

`_write_filter_audit` updated to include `scorer` field in every audit record, plus
`svm_model_name` and `svm_model_path` when `scorer == "svm"`.

### `tools/cli/research_prefetch_discover.py`

Three new optional arguments added:

- `--filter-scorer {lexical,svm}` — default `lexical`
- `--svm-model PATH` — required when scorer=svm
- `--svm-metadata PATH` — optional

Validation: `scorer=svm + no --svm-model` → rc=1 with clear error.

Scorer initialization block replaced with scorer-dispatch block:

- `filter_scorer == "svm"` → `SvmRelevanceScorer(SvmRuntimeConfig(...))`
- `filter_scorer == "lexical"` (default) → existing `RelevanceScorer(load_filter_config(...))` path

`CandidateInput` imported unconditionally from `scorer` module so it is available to
both scorers.

---

## Exact CLI Flags Added

### research-acquire

```
--prefetch-filter-scorer {lexical,svm}
    Relevance filter scorer backend (default: lexical).
    lexical: keyword-based v1.1 scorer (production default).
    svm: trained SVM model — requires --prefetch-svm-model;
    enforce mode is blocked for SVM until >=150 labels and Director approval.

--prefetch-svm-model PATH
    Path to trained SVM .joblib model artifact
    (required when --prefetch-filter-scorer svm and mode is not off).

--prefetch-svm-metadata PATH
    Path to SVM metadata JSON (optional; inferred from model path when omitted).
```

### research-prefetch-discover

```
--filter-scorer {lexical,svm}
    Relevance filter scorer backend (default: lexical).
    svm: use trained SVM model — requires --svm-model.

--svm-model PATH
    Path to trained SVM .joblib model artifact (required when --filter-scorer svm).

--svm-metadata PATH
    Path to SVM metadata JSON (optional; inferred from model path when omitted).
```

---

## Enforce-Block Behavior

```
$ python -m polytool research-acquire \
    --url https://arxiv.org/abs/2301.12345 --source-family academic --no-eval \
    --prefetch-filter-mode enforce \
    --prefetch-filter-scorer svm \
    --prefetch-svm-model /path/to/model.joblib

Error: SVM enforce is blocked until >=150 labels and Director approval.
Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
[exit code 1]
```

---

## Tests Written

### tests/test_ris_research_acquire_cli.py — `TestSvmScorerIntegration` (7 tests)

| Test | What it verifies |
|------|-----------------|
| `test_svm_enforce_blocked` | scorer=svm + enforce → rc=1, "blocked" in stderr |
| `test_svm_requires_model_path_when_mode_active` | scorer=svm + dry-run + no model → rc=1 |
| `test_svm_off_mode_does_not_require_model_path` | mode=off → no model needed, rc=0 |
| `test_svm_dry_run_logs_svm_decision_to_stderr` | scorer=svm dry-run → audit has scorer=svm, svm_model_name |
| `test_svm_hold_review_queues_with_svm_audit` | hold-review REVIEW → queued; audit scorer=svm |
| `test_svm_hold_review_allow_proceeds_normally` | hold-review ALLOW → not queued |
| `test_lexical_default_unaffected_by_new_flags` | existing enforce+lexical path unchanged |

### tests/test_ris_prefetch_discovery.py — `TestSvmScorerDiscover` (3 tests)

| Test | What it verifies |
|------|-----------------|
| `test_svm_requires_model_path` | --filter-scorer svm without --svm-model → rc=1 |
| `test_lexical_default_unchanged` | default lexical still works; SVM not imported |
| `test_svm_scorer_called_when_specified` | --filter-scorer svm uses SvmRelevanceScorer |

All tests monkeypatch `SvmRelevanceScorer.score` with a canned `FilterDecision`. No real
model is loaded in tests.

---

## Commands Run

### `python -m pytest tests/test_ris_research_acquire_cli.py -q`

```
39 passed in 0.89s
```

### `python -m pytest tests/test_ris_prefetch_discovery.py -q`

```
49 passed in 0.64s
```

### `python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py -q`

```
134 passed in 3.87s
```

### Full suite (all five suites together)

```
222 passed in 4.78s
```

### `python -m polytool research-acquire --help` (with PYTHONIOENCODING=utf-8)

Exit code 0. New flags visible: `--prefetch-filter-scorer {lexical,svm}`,
`--prefetch-svm-model PATH`, `--prefetch-svm-metadata PATH`.

### `python -m polytool research-prefetch-discover --help`

Exit code 0. New flags visible: `--filter-scorer {lexical,svm}`, `--svm-model PATH`,
`--svm-metadata PATH`.

---

## Constraints Met

- Lexical v1.1 is default. No existing behavior changed.
- SVM is default-off. Only active with explicit `--prefetch-filter-scorer svm`.
- SVM enforce is blocked at the CLI layer with a clear error message.
- `mode=off` does not import or instantiate the SVM scorer even if scorer flag is present.
- No changes to `svm_scorer.py`, `svm_training.py`, `labels.jsonl`, model artifacts,
  L2/L4/Marker IPC code.
- No label edits, no migrations.

---

## Windows-Specific Fix

Initial help text used `≥` (U+2265). Windows cp1252 shell raised `UnicodeEncodeError`
on `--help`. Replaced with `>=` throughout. This is a known PolyTool Windows gotcha.

---

## Open Questions / Next Steps

1. **Model selection for production.** Evidence run used `BAAI/bge-large-en-v1.5` (SPECTER2
   blocked by AdapterHub/PEFT mismatch). Operator must decide the production embedding model
   before enabling SVM in any non-dry-run mode.
2. **Label corpus expansion.** Current corpus is 61 labels (30 allow / 31 reject). SVM
   enforce is blocked until >=150 labels and Director approval. Continue queueing via
   `research-prefetch-discover --decision-filter all --include-allow`.
3. **Operator validation run.** Try:
   ```
   python -m polytool research-acquire --url <url> --source-family academic --no-eval \
     --prefetch-filter-mode dry-run \
     --prefetch-filter-scorer svm \
     --prefetch-svm-model artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib \
     --review-dir artifacts/research/acquisition_reviews
   ```
4. **Feature doc and CURRENT_STATE.md** — update after operator validation run confirms
   the integration works end-to-end.

---

## Codex Review Summary

Tier: Recommended. Files changed are CLI wiring and tests only; no execution/risk/kill-switch
code involved.
Issues found: none blocking.
Issues carried forward: model selection, dependency declaration, corpus expansion.
