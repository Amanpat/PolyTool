# Fix: L3 v1 SVM Train CLI — Codex Review Blockers

Date: 2026-05-06
Author: Claude Code
Scope: Fix Codex FAIL findings from `2026-05-06_codex-review-l3-v1-svm-train-cli.md`.

## Files Changed

| File | Why |
|---|---|
| `tools/cli/research_prefetch_svm_train.py` | Fix P1 config kwarg, add lexical note output, add joblib dep check, fix cache default |
| `tests/test_ris_prefetch_svm_train_cli.py` | Update fake config/result to match real API; add tests for all four fixes |
| `packages/research/relevance_filter/svm_training.py` | Separate joblib import so missing-joblib raises a clear domain error naming joblib |

## Codex Findings and Resolutions

### P1 (Blocking): CLI/core config contract mismatch — `labels_path` vs `label_path`

**Problem:** `tools/cli/research_prefetch_svm_train.py` line 288 passed
`SvmTrainingConfig(labels_path=...)` but the real dataclass uses `label_path`.
A non-dry-run invocation raised `TypeError: SvmTrainingConfig.__init__() got an
unexpected keyword argument 'labels_path'` before any training ran.

The CLI tests all passed because `_make_fake_svm_module` also used `labels_path=` in
`FakeSvmTrainingConfig.__init__`, masking the mismatch.

**Resolution:**
- Changed CLI config construction to `label_path=labels_path`.
- Updated `FakeSvmTrainingConfig` in the test file to use `label_path` consistently.
- Updated `test_train_config_has_correct_args` to assert `cfg.label_path`.
- Added `TestRealConfigSignature` class with three tests:
  - `test_label_path_kwarg_accepted` — constructs real `SvmTrainingConfig(label_path=...)`, asserts no error.
  - `test_labels_path_kwarg_rejected` — asserts `TypeError` on `labels_path=` to catch future regression.
  - `test_config_signature_has_label_path_not_labels_path` — introspects `inspect.signature`.

### P1 (Blocking): CLI output omits lexical baseline comparison note

**Problem:** `result.lexical_baseline_note` was never included in JSON or human-readable
output. The work packet acceptance criteria require the Lexical v1.1 Scenario B 5.88%
comparison to appear in the evaluation report.

**Resolution:**
- Added `"lexical_baseline_note": result.lexical_baseline_note` to the JSON output dict.
- Added `print(f"\n  baseline        : {result.lexical_baseline_note}")` to human-readable output.
- Added `lexical_baseline_note: str = "Lexical v1.1 Scenario B: 5.88% off-topic rate"` to `_FakeSvmResult`.
- Added two new tests: `test_train_json_has_lexical_baseline_note` and
  `test_train_human_readable_has_lexical_baseline_note`, both asserting `"5.88"` or
  `"Scenario B"` appears in the respective output.

### P2 (Non-blocking, required before closeout): joblib dep check incomplete

**Problem:** `_check_ml_deps()` checked `sklearn` and `sentence_transformers` but not
`joblib`. If joblib was absent in a broken environment, the failure surfaced at training
time as exit 2 (generic runtime error) rather than exit 1 (graceful dependency error),
with the misleading message "scikit-learn is required".

**Resolution:**
- Added `import joblib` check to `_check_ml_deps()`.
- Separated the `import joblib` block in `svm_training.py` into its own `try/except`
  with an explicit `SvmMissingDepsError("joblib is required...")` so that missing joblib
  gives a specific error even when called from code that bypasses the CLI dep check.
- Added `test_missing_joblib_returns_1` to `TestMissingMlDeps`: monkeypatches
  `_check_ml_deps` to return `["joblib"]`, asserts exit 1 and "joblib" in stderr.

### P3 (Non-blocking): embedding cache default path does not match packet

**Problem:** `_DEFAULT_EMBEDDING_CACHE_DIR` was `artifacts/research/svm_filter_embeddings`
but the work packet specifies `artifacts/research/svm_filter_models/embeddings`.

**Resolution:**
- Changed `_DEFAULT_EMBEDDING_CACHE_DIR = _DEFAULT_OUTPUT_DIR / "embeddings"` so it is
  `artifacts/research/svm_filter_models/embeddings` and stays in sync if `_DEFAULT_OUTPUT_DIR` ever changes.
- Updated `--embedding-cache-dir` help text to show the corrected default.
- Added `TestDefaultEmbeddingCacheDir::test_default_embedding_cache_under_models_dir`:
  runs `--dry-run --json`, parses output, asserts `svm_filter_models` is in the path
  and the path ends with `embeddings`.

## Commands Run

```
python -m pytest tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py -q --tb=short
```

Result: **81 passed in 3.45s** (up from 39 + 35 = 74; 7 new tests added).

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_prefetch_discovery.py -q --tb=short
```

Result: **131 passed in 1.84s** — no regressions.

```
python -m polytool research-prefetch-svm-train --help
```

Result: exits 0; `--embedding-cache-dir` default shows `svm_filter_models/embeddings`.

```
python -m polytool research-prefetch-svm-train --dry-run --json
```

Result: exits 0; `embedding_cache_dir` path ends with `svm_filter_models\embeddings`.

```
python -c "from packages.research.relevance_filter.svm_training import SvmTrainingConfig; ..."
```

Result: `OK label_path= labels.jsonl` — no TypeError.

## Is real local train/eval now safe?

Yes, the two blocking issues have been resolved:
1. Non-dry-run CLI now constructs `SvmTrainingConfig(label_path=...)` correctly.
2. CLI output (both JSON and human-readable) includes the lexical baseline note.

The operator can run real training with:
```
python -m polytool research-prefetch-svm-train \
  --labels artifacts/research/svm_filter_labels/labels.jsonl \
  --output-dir artifacts/research/svm_filter_models \
  --random-state 42
```

Model weights (allenai/specter2) must be present in the local sentence-transformers
cache or will be downloaded on first run.

## Open Questions

None blocking. SVM scoring integration into acquisition/discovery remains default-off
and blocked until the operator explicitly enables it after reviewing eval results.

## Codex Review Summary

Review tier: Recommended (RIS filtering/training CLI and core, no live trading code).
Issues found: 2 blocking, 2 non-blocking.
Issues addressed: All 4 resolved and covered by new tests.
