# L3 v1 SVM Training Core — Implementation

**Date:** 2026-05-06
**Track:** Research Intelligence System (L3 v1)
**Status:** Complete — core train/eval logic shipped; CLI layer (Prompt B) not yet wired

---

## Summary

Implemented the offline SVM training and evaluation core for the L3 v1 topic filter.
The module can load labels, embed texts via an injectable provider, train/evaluate
a LinearSVC pipeline deterministically, write artifact metadata, and pass 39 tests
without downloading model weights or touching the network.

No production enforcement was added. The SVM is not wired into any acquisition or
discovery path. All existing L3/L3.1/L3.2 tests remain green.

---

## Files Changed

| File | Type | Why |
|------|------|-----|
| `packages/research/relevance_filter/svm_training.py` | NEW | Core train/eval module — `SvmTrainingConfig`, `SvmTrainingResult`, `LabeledExample`, `SvmMissingDepsError`, `train_and_evaluate_svm`, `load_labeled_examples` |
| `tests/test_ris_prefetch_svm_train.py` | NEW | 39 offline tests covering label loading, min-per-class gate, determinism, cache reuse, metadata ledger, model artifact, and missing-dep behavior |
| `pyproject.toml` | MODIFIED | Added `[ris-svm]` optional group (`scikit-learn>=1.3.0`, `sentence-transformers>=2.2.0`, `joblib>=1.3.0`); added `packages.research.relevance_filter` to packages list |

---

## Commands Run and Results

```
python -m pytest tests/test_ris_prefetch_svm_train.py -q --tb=short
→ 39 passed in 10.15s

python -m pytest tests/test_ris_relevance_filter.py -q --tb=short
→ 53 passed in 0.52s

python -m pytest tests/test_ris_prefetch_discovery.py -q --tb=short
→ 46 passed in 0.54s
```

No failures. No new warnings.

---

## API Contract Implemented

Module: `packages.research.relevance_filter.svm_training`

### Classes / functions

```python
class SvmMissingDepsError(RuntimeError): ...

@dataclass
class SvmTrainingConfig:
    label_path: Path
    output_dir: Path
    embedding_cache_dir: Path
    model_name: str
    random_state: int = 42
    test_size: float = 0.25
    min_per_class: int = 5

@dataclass
class LabeledExample:
    candidate_id: str
    text: str           # title + note + source_url joined with spaces
    label: str          # "allow" | "reject"
    source_url: str
    title: str

@dataclass
class SvmTrainingResult:
    metrics: dict       # accuracy, precision/recall/f1 per class + macro, train_size, test_size
    confusion_matrix: list  # 2×2 [[TP_allow, FN_allow], [FP_allow, TN_allow]]
    model_artifact_path: Optional[str]  # .joblib path, or None when skipped
    metadata_path: str
    label_count: int
    allow_count: int
    reject_count: int
    random_state: int
    lexical_baseline_note: str  # "Lexical v1.1 Scenario B: 5.88% off-topic rate"
    skipped_training: bool
    skip_reason: str

def load_labeled_examples(label_path: Path) -> list[LabeledExample]: ...

def train_and_evaluate_svm(
    config: SvmTrainingConfig,
    embedding_provider: Optional[Callable[[list[str]], list[list[float]]]] = None,
) -> SvmTrainingResult: ...
```

### Embedding provider contract

```python
embedding_provider(texts: list[str]) -> list[list[float]]
```

Each call returns one float vector per input text. Vectors need not be unit-normalised.
When `embedding_provider=None`, the module uses `sentence_transformers.SentenceTransformer`
with `config.model_name`. Pass a mock here for offline tests.

### Embedding cache

- Cache key: `sha256(f"{model_name}:{text}")` — stable across processes
- Cache path: `{embedding_cache_dir}/{key[:2]}/{key}.json`
- First run embeds uncached texts and writes them; subsequent runs load from disk
- Different `model_name` values produce different cache entries

### Metadata ledger fields (written to `output_dir/svm_metadata_*.json`)

| Field | Type | Description |
|-------|------|-------------|
| `label_count` | int | Total loaded examples |
| `allow_count` | int | Examples with label=allow |
| `reject_count` | int | Examples with label=reject |
| `train_size` | int | Training set size |
| `eval_size` | int | Evaluation set size |
| `seed` | int | `random_state` used |
| `timestamp` | str | ISO-8601 UTC |
| `sklearn_version` | str | `sklearn.__version__` |
| `model_type` | str | "LinearSVC" |
| `model_params` | dict | `LinearSVC.get_params()` |
| `embedding_model` | str | `config.model_name` |
| `metrics` | dict | accuracy, precision/recall/f1 per class + macro |
| `confusion_matrix` | list | 2×2 nested list |
| `lexical_baseline_note` | str | Baseline reference string |
| `skipped_training` | bool | True if min_per_class gate fired |
| `skip_reason` | str | Human-readable reason if skipped |

---

## Design Decisions

### LinearSVC over SVC(rbf)

Chose `LinearSVC` with `StandardScaler` as recommended in the activation dev log.
With 61 labeled examples, linear regularisation generalises better than RBF.
`SVC(probability=True)` is a future option if calibrated confidence scores are needed
for the scoring path.

### text = title + note + source_url

Built embedding text from all three available fields per the scope spec. The `note`
field is operator-authored free text and adds meaningful signal (e.g., "off-topic
healthcare" vs. "relevant prediction-market microstructure paper"). The `source_url`
adds domain signal (arXiv category hint in the path).

### Optional imports are lazy

All sklearn/numpy/joblib imports happen inside `train_and_evaluate_svm()` rather
than at module level. This preserves the module's importability even when the
optional deps are absent and allows `load_labeled_examples()` to work at all times.

### Cache uses 2-char prefix sharding

`{key[:2]}/` subdirectory avoids a flat directory with 61+ files. Consistent with
common cache layout conventions.

---

## Open Questions for CLI / Integration (Prompt B)

1. **CLI command name** — activation dev log suggests `research-prefetch-svm-train` or
   `research-prefetch-filter-train`. Prompt B should pick one and register it in
   the CLI router.

2. **Default model name** — `config.model_name` has no default in `SvmTrainingConfig`.
   Prompt B CLI should default to `"allenai/specter2"` (canonical paper embedding model)
   and expose `--model-name` to override.

3. **Default output/cache dirs** — CLI should default `output_dir` to
   `artifacts/research/svm_filter_models/` and `embedding_cache_dir` to
   `artifacts/research/svm_filter_models/embeddings/`. Both are gitignored.

4. **Evaluation report format** — `SvmTrainingResult.metrics` is a dict. Prompt B
   should pretty-print a human-readable table (precision/recall/F1 per class + macro)
   with the lexical baseline comparison line.

5. **Cross-validation path** — current implementation uses a single train/test split
   (test_size=0.25). The activation dev log recommends 5-fold stratified CV as primary
   with the fixed-seed holdout as secondary. If Prompt B wants CV, extend
   `SvmTrainingConfig` with a `cv_folds: Optional[int]` field and add the CV branch
   to `train_and_evaluate_svm`.

6. **SVMRelevanceScorer** — `svm_scorer.py` is not yet implemented. It would wrap a
   saved `.joblib` pipeline for inference-time scoring, parallel to `RelevanceScorer`.
   This is deferred until evaluation gates pass and the operator decides to enable SVM.

7. **pyproject.toml `[ris-svm]` not in `[all]`** — deliberately not added to `[all]`
   to avoid pulling in large embedding deps for non-RIS installs. Prompt B CLI should
   document the install step.

---

## Acceptance Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| Graceful degradation on missing deps | ✅ PASS | `SvmMissingDepsError` with pip install hint; 3 tests cover this |
| Determinism (same seed → same metrics) | ✅ PASS | `test_two_runs_produce_identical_metrics` and `test_two_runs_produce_identical_confusion_matrix` |
| Offline tests (no model download) | ✅ PASS | All 39 tests use `_fake_provider` (hashlib-based, no network) |
| Regression (L3/L3.1/L3.2 green) | ✅ PASS | 53 + 46 = 99 existing tests pass |
| Labels read-only (no format change) | ✅ PASS | `_read_jsonl` used; no writes to label file |
| Default-off enforcement | ✅ PASS | No CLI wiring; SVM not active in any pipeline mode |
