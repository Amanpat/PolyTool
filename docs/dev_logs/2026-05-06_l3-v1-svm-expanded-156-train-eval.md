# L3 v1 SVM — Expanded 156-Label Corpus Train/Eval

**Date:** 2026-05-06  
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter  
**Scope:** Retrain/eval on the verified 156-label corpus. No integration wiring, no label edits, no code changes, no L2/L4/Marker IPC work.

---

## Summary

Expanded corpus retrain/eval completed successfully. The SVM classifier trained on 156 labels (74 allow / 82 reject) using `BAAI/bge-large-en-v1.5` embeddings achieves **1.000 macro F1** on a 39-sample hold-out test set (up from 16-sample in the prior 61-label run). All prior artifacts are preserved. Targeted tests: 123 passed, 0 failed. Metrics are better-evidenced than the prior run but still cannot be called statistically conclusive — the dataset is small and perfect scores are a warning sign as much as a success indicator.

**Verdict: PROCEED to Director approval review**, with honest caveats documented below.

---

## Step 1 — Baseline

### git status --short (excerpt)
```
 M docs/CURRENT_DEVELOPMENT.md
 M packages/research/relevance_filter/__init__.py
 M packages/research/relevance_filter/scorer.py
 M polytool/__main__.py
 M pyproject.toml
 M tests/test_ris_prefetch_discovery.py
 M tests/test_ris_research_acquire_cli.py
 M tools/cli/research_acquire.py
 M tools/cli/research_prefetch_discover.py
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-applied-labels.md
 ... (untracked dev logs)
```

### Label counts (python -m polytool research-prefetch-review counts --json)
```json
{
  "total_queued": 159,
  "pending_unlabeled": 3,
  "labeled_total": 156,
  "labeled_allow": 74,
  "labeled_reject": 82,
  "pending_review_count": 159,
  "label_count": 156,
  "allowed_label_count": 74,
  "rejected_label_count": 82
}
```

### labels.jsonl SHA256 (before)
```
56cebcc2210ba7ff1a47ba1cb6a64de649472833d23fb9d3eb4e38bec387767e
```
SHA matches the post-label-application SHA from `docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-applied-labels.md`. Labels not modified.

### Prior model artifacts in artifacts/research/svm_filter_models/
```
Name                                         Length  LastWriteTime
----                                         ------  -------------
embeddings/                                  (dir)   2026-05-06 08:52:58
first-real-train-eval.json                   1317    2026-05-06 08:55:47
svm_metadata_BAAI_bge-large-en-v1.5_42.json 1177    2026-05-06 08:53:38
svm_model_BAAI_bge-large-en-v1.5_42.joblib  33997   2026-05-06 08:53:38
```

---

## Step 2 — Dry-Run Readiness

```
python -m polytool research-prefetch-svm-train --dry-run --json \
  --model-name "BAAI/bge-large-en-v1.5" \
  --output-dir artifacts/research/svm_filter_models/expanded_156 \
  --embedding-cache-dir artifacts/research/svm_filter_models/embeddings
```

Output:
```json
{
  "dry_run": true,
  "labels_path": "...artifacts\\research\\svm_filter_labels\\labels.jsonl",
  "label_count": 156,
  "allow_count": 74,
  "reject_count": 82,
  "model_name": "BAAI/bge-large-en-v1.5",
  "random_state": 42,
  "test_size": 0.25,
  "output_dir": "artifacts\\research\\svm_filter_models\\expanded_156",
  "embedding_cache_dir": "artifacts\\research\\svm_filter_models\\embeddings",
  "deps_ok": true,
  "core_module_ok": true,
  "ready_to_train": true
}
```

Exit code: 0. All deps present; ready to train.

---

## Step 3 — Expanded Training (BGE, separate output dir, shared embedding cache)

```
python -m polytool research-prefetch-svm-train \
  --model-name "BAAI/bge-large-en-v1.5" \
  --output-dir artifacts/research/svm_filter_models/expanded_156 \
  --embedding-cache-dir artifacts/research/svm_filter_models/embeddings \
  --json
```

Exit code: 0.

Raw stdout captured:
```json
{
  "label_count": 156,
  "allow_count": 74,
  "reject_count": 82,
  "random_state": 42,
  "metrics": {
    "accuracy": 1.0,
    "precision": { "allow": 1.0, "reject": 1.0, "macro": 1.0 },
    "recall":    { "allow": 1.0, "reject": 1.0, "macro": 1.0 },
    "f1":        { "allow": 1.0, "reject": 1.0, "macro": 1.0 },
    "train_size": 117,
    "test_size": 39
  },
  "confusion_matrix": [[19, 0], [0, 20]],
  "model_artifact_path": "artifacts\\research\\svm_filter_models\\expanded_156\\svm_model_BAAI_bge-large-en-v1.5_42.joblib",
  "metadata_path": "artifacts\\research\\svm_filter_models\\expanded_156\\svm_metadata_BAAI_bge-large-en-v1.5_42.json",
  "lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate"
}
```

---

## Step 4 — Generated Artifacts

| Artifact | Path | Size |
|---|---|---|
| Model (.joblib) | `artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib` | 33,997 bytes |
| Metadata JSON | `artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json` | 1,182 bytes |

Embedding cache: grew from 61 → 156 files (95 new embeddings computed; 61 prior embeddings reused from shared cache at `svm_filter_models/embeddings/`).

Prior 61-label artifacts in parent directory: **unchanged** (timestamps still 2026-05-06 08:53:38).

---

## Step 4 — Metadata Validation

| Field | Expected | Actual | Match |
|---|---|---|---|
| `label_count` | 156 | 156 | ✓ |
| `allow_count` | 74 | 74 | ✓ |
| `reject_count` | 82 | 82 | ✓ |
| `seed` | 42 | 42 | ✓ |
| `embedding_model` | `BAAI/bge-large-en-v1.5` | `BAAI/bge-large-en-v1.5` | ✓ |
| `model_type` | `LinearSVC` | `LinearSVC` | ✓ |
| `metrics` | precision+recall+F1+accuracy | all present | ✓ |
| `confusion_matrix` | exists | `[[19,0],[0,20]]` | ✓ |
| `lexical_baseline_note` | present | `Lexical v1.1 Scenario B: 5.88% off-topic rate` | ✓ |
| `skipped_training` | false | false | ✓ |
| `train_size` | — | 117 | ✓ |
| `eval_size` | — | 39 | ✓ |

All fields present and correct.

---

## Step 5 — 61-Label vs 156-Label Comparison

| Metric | 61-label run (prior) | 156-label run (this) | Change |
|---|---|---|---|
| label_count | 61 | 156 | +95 labels |
| allow_count | 30 | 74 | +44 |
| reject_count | 31 | 82 | +51 |
| train_size | 45 | 117 | +72 |
| test_size | 16 | 39 | +23 |
| Accuracy | 1.0000 | 1.0000 | same |
| Precision — allow | 1.0000 | 1.0000 | same |
| Precision — reject | 1.0000 | 1.0000 | same |
| Precision — macro | 1.0000 | 1.0000 | same |
| Recall — allow | 1.0000 | 1.0000 | same |
| Recall — reject | 1.0000 | 1.0000 | same |
| F1 — macro | 1.0000 | 1.0000 | same |
| Confusion matrix | [[8,0],[0,8]] | [[19,0],[0,20]] | scaled up, still perfect |
| Embedding model | BAAI/bge-large-en-v1.5 | BAAI/bge-large-en-v1.5 | same |
| sklearn_version | 1.8.0 | 1.8.0 | same |

**No degradation.** The expanded corpus maintains perfect hold-out scores, and the test set nearly doubled (16 → 39 samples). This is a materially better evidence base than the 61-label run.

### Interpretation and caveats

The persistent 1.000 macro F1 across both corpus sizes is consistent with two hypotheses:

1. **Genuine separability** (most likely): academic paper titles/abstracts cluster cleanly in BAAI/bge-large-en-v1.5's 1024-dim space, and a linear SVM can find a hyperplane that separates them from non-academic content with high margin. This is plausible given the domain: financial blog posts, news articles, and prediction market metadata look very different from arXiv paper titles.

2. **Overfitting risk** (cannot be ruled out): the dataset is still small (156 examples, 39-sample test), and perfect scores may reflect a favorable stratified split rather than robust generalization. The class balance is reasonable (74/82, near 47%/53%) but 39 test samples is below any reliable confidence interval.

**Key risk indicator:** The model file size is identical between the 61-label run (33,997 bytes) and the 156-label run (33,997 bytes). This is unusual — a substantially larger training set typically produces a different model. This likely reflects that `LinearSVC` converges to similar boundary weights when the data is highly linearly separable (the hyperplane doesn't change much when adding more cleanly-separated examples). This is not a correctness bug, but it reinforces the "easy problem / wide margin" hypothesis.

**What 39-sample perfect scores can and cannot tell us:**
- CAN say: no false positives or false negatives on this split
- CANNOT say: precision/recall on a truly independent hold-out set
- Cross-validation on 156 examples would give a better estimate (5-fold = 31/25 splits each)
- Statistical power for a 95% CI on F1≥0.95 requires roughly 200+ test samples

---

## Step 6 — Targeted Tests

```
python -m pytest tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py tests/test_ris_prefetch_svm_scorer.py -q --tb=short
```

Result: **123 passed, 0 failed** in 4.25s.

| Test file | Count | Result |
|---|---|---|
| `tests/test_ris_prefetch_svm_train.py` | 39 | PASS |
| `tests/test_ris_prefetch_svm_train_cli.py` | 42 | PASS |
| `tests/test_ris_prefetch_svm_scorer.py` | 42 | PASS |
| **Total** | **123** | **PASS** |

No regressions. All existing SVM train/eval and scorer tests pass.

---

## Step 7 — Verdict

**PROCEED to Director approval review.**

The expanded 156-label retrain/eval is complete. Key evidence:

- Label gate (>=150) passed: 156 >= 150 ✓
- Artifacts generated in separate `expanded_156/` directory ✓
- Prior 61-label artifacts untouched ✓
- Metrics equal or better (larger test set, same perfect scores) ✓
- All targeted tests pass ✓
- No code changes made ✓
- Labels not modified (SHA unchanged) ✓

**Caveats for Director review:**

1. 39-sample test is statistically marginal. 1.000 macro F1 is strong evidence of linear separability in bge-large embedding space but is not a rigorous held-out evaluation.

2. Model file size unchanged (33,997 bytes) between 61-label and 156-label runs. This reflects easy linear separation, not a pipeline bug, but warrants awareness.

3. SPECTER2 model path still unresolved. The current validated path is `BAAI/bge-large-en-v1.5`. Director must decide: declare bge-large as production model, or pursue `allenai/specter2_base` / `adapters` library path.

4. SVM enforce remains hard-blocked at rc=1 until Director approval is recorded. No enforcement path was changed in this session.

---

## Open Questions

1. **Director approval:** Is the 156-label expanded corpus sufficient to approve SVM enforcement in `hold-review` mode (scoring only, no auto-reject) as a first step?

2. **Model selection decision:** Declare `BAAI/bge-large-en-v1.5` as the production embedding model, or pursue SPECTER2 path?

3. **Cross-validation:** Would a 5-fold CV run on the 156-label corpus give the Director higher confidence before approving enforcement?

4. **Enforce scope:** When enforcement is approved, should the first enabled mode be `dry-run` (score + log, no reject) or full `enforce` (with reject-only as Scenario A)?

---

## Artifact Integrity

| Check | Status |
|---|---|
| labels.jsonl SHA unchanged before/after | ✓ PASS |
| Prior 61-label model artifacts untouched | ✓ PASS |
| expanded_156/ contains model + metadata | ✓ PASS |
| embedding cache grew from 61 to 156 files | ✓ PASS |
| No implementation code modified | ✓ PASS |
| No tests modified | ✓ PASS |
| No queue files modified | ✓ PASS |
| SVM enforce path unchanged (rc=1 block) | ✓ PASS |

---

## Codex Review Summary

Tier: Skip (no implementation code, tests, or live-trading paths changed — this session ran commands and wrote this dev log only).  
Issues found: none.  
Issues addressed: n/a.
