---
title: L3 V1 Svm Runtime Scorer
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_l3-v1-svm-runtime-scorer.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3 v1 SVM Runtime Scorer

**Date:** 2026-05-06  
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter  
**Scope:** Runtime scorer only. No acquisition/discovery wiring, no enforcement mode, no label/artifact edits, no L2/L4/Marker IPC work.

---

## Summary

Implemented the SVM runtime scorer layer for L3 v1. A trained `.joblib` artifact + metadata JSON can now be loaded and used to score `CandidateInput` objects via a clean `SvmRelevanceScorer` API. All 42 new tests pass offline. All 134 existing L3/train/lexical tests pass. No regressions.

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `packages/research/relevance_filter/scorer.py` | Added 5 optional audit fields to `FilterDecision` | Required by API contract: `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, `svm_lexical_baseline_note` |
| `packages/research/relevance_filter/svm_scorer.py` | New file | Runtime scorer implementation |
| `packages/research/relevance_filter/__init__.py` | Added `SvmRuntimeConfig`, `SvmRelevanceScorer`, `SvmModelLoadError`, `SvmMissingDepsError` to `__all__` | Stable public API re-export |
| `tests/test_ris_prefetch_svm_scorer.py` | New file — 42 tests | Offline coverage per test plan |
| `docs/dev_logs/2026-05-06_l3-v1-svm-runtime-scorer.md` | New file | This dev log |

### `FilterDecision` backward compatibility

New fields all have defaults (`scorer="lexical"`, others `""` / `0`) so all existing callers using keyword args are unaffected. The lexical `RelevanceScorer` does not set them — they remain at default. New `SvmRelevanceScorer` sets `scorer="svm"` and populates the `svm_*` fields.

---

## API Contract Implemented

```python
# Configuration
SvmRuntimeConfig(
    model_path: str,
    metadata_path: Optional[str] = None,   # inferred if omitted
    threshold_allow: float = 0.50,
    threshold_review: float = 0.35,
)

# Scorer
SvmRelevanceScorer(config, embedding_provider=None)
SvmRelevanceScorer.score(candidate: CandidateInput) -> FilterDecision

# Errors
SvmModelLoadError(RuntimeError)    # missing/corrupt model or metadata
SvmMissingDepsError(RuntimeError)  # joblib / numpy / sentence-transformers absent
```

### Decision-function calibration

LinearSVC does not expose `predict_proba()`. The scorer derives an "allow confidence" via:

```python
allow_confidence = sigmoid(-df_value)
```

where `df_value` is `pipeline.decision_function(X)[0]`.

With sklearn's alphabetical class ordering (`['allow', 'reject']`):
- positive `df_value` → model leans "reject" → `allow_confidence → 0.0`
- `df_value ≈ 0` → decision boundary → `allow_confidence ≈ 0.5`
- negative `df_value` → model leans "allow" → `allow_confidence → 1.0`

The scorer also handles the rare case where 'allow' is not `classes_[0]` by checking `classes_.index("allow")` and flipping the sign.

**This is NOT a calibrated probability.** It is a monotone confidence-like value suited for thresholding. The module docstring documents this clearly.

### Metadata inference

When `metadata_path=None`, the scorer infers the path by replacing the `svm_model_` prefix with `svm_metadata_` and `.joblib` with `.json` in the same directory. This matches the filenames written by `train_and_evaluate_svm()` in `svm_training.py`.

### Embedding text at inference time

Training used: `title + operator_note + source_url` (operator notes available in LabelStore records).  
Inference uses: `title + abstract + source_url` (notes are not available on new candidates).

This is a minor distribution shift. The abstract is a better semantic proxy for training content than the operator note, so the shift is expected to be benign. Documented as an open question for the CLI integration prompt.

---

## Commands Run

### Scorer tests
```
python -m pytest tests/test_ris_prefetch_svm_scorer.py -v --tb=short
→ 42 passed in 1.85s
```

### Regression tests
```
python -m pytest tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py tests/test_ris_relevance_filter.py -q --tb=short
→ 134 passed in 3.85s
```

### Total: 176 tests, 0 failed, 0 regressions.

---

## Decisions Made

1. **`FilterDecision` extension vs separate dataclass:** Added 5 optional fields with defaults to the existing `FilterDecision`. This keeps the return type uniform across lexical and SVM scorers — callers don't need to branch on type. Backward compatible.

2. **`SvmModelLoadError` as a distinct error class:** Separates file/load failures (`SvmModelLoadError`) from missing-package failures (`SvmMissingDepsError`). CLI integration can catch each independently.

3. **Lazy loading:** `_load()` is deferred to the first `score()` call. This means `SvmRelevanceScorer()` is cheap to instantiate and the error fires at use-time with a clear message — same pattern used by `RelevanceScorer`.

4. **Default embedding provider caching:** `_default_provider` is created once on first use and cached on the scorer instance. Repeated `score()` calls reuse the same `SentenceTransformer` object.

5. **Classes sign convention handled dynamically:** `classes_.index("allow")` is checked rather than hardcoded. This handles alphabetical reordering defensively.

---

## Open Questions for CLI Integration (Prompt B)

1. **Train/score text mismatch:** Training text used `operator_note`; scoring text uses `abstract`. Consider re-training with title + abstract as the text if this causes classification drift on new candidates.

2. **Model selection still unresolved:** `BAAI/bge-large-en-v1.5` is cached and works; `allenai/specter2` is blocked by AdapterHub/PEFT mismatch. Operator must decide before shipping the `--prefetch-filter-mode svm` flag (see evidence pass dev log).

3. **`peft` in pyproject.toml:** Still needs to be added to `ris-svm` optional extras if SPECTER2 is chosen.

4. **No caching at score time:** The runtime scorer re-embeds each candidate on every call. For bulk-prefetch use the CLI layer should batch candidates and use the same embedding cache layer from `svm_training.py` (`_embed_with_cache`) rather than calling `score()` in a loop. This is a CLI concern, not a scorer concern.

5. **Enforce-mode gating:** The SVM scorer must remain default-off. Only the `--prefetch-filter-mode svm` flag (or equivalent config) should activate it. No enforcement path should be enabled until label corpus reaches 150+.

---

## Codex Review Summary

Review tier: Recommended (RIS filtering/scoring — no live trading, risk, or execution code).  
Issues found: none blocking integration.  
Issues carried forward (already in `CURRENT_DEVELOPMENT.md`): model selection, `peft` dep, corpus expansion before enforce mode.
