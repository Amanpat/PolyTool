---
title: L3 V1 Svm Train Cli
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — L3 v1 SVM Train/Eval CLI

**Date:** 2026-05-06  
**Feature:** RIS L3 v1 SVM Topic Filter — CLI and command registration (Prompt B)  
**Scope:** CLI files + command registration only  

---

## Objective

Add the `research-prefetch-svm-train` CLI command that wraps the Prompt A core API
(`SvmTrainingConfig`, `train_and_evaluate_svm`) without implementing the core itself.
`python -m polytool research-prefetch-svm-train --help` must work, the CLI must call
the Prompt A API contract when the core module is available, and all tests must run
offline without downloading model weights.

---

## Files Changed

| File | Reason |
|------|--------|
| `tools/cli/research_prefetch_svm_train.py` | New CLI module — entry point, arg parsing, dep checks, label validation, core call, output formatting |
| `polytool/__main__.py` | Register `research_prefetch_svm_train_main` entrypoint, add to `_COMMAND_HANDLER_NAMES`, add help line in `print_usage()` |
| `tests/test_ris_prefetch_svm_train_cli.py` | New test file — 35 offline tests covering all acceptance gates |
| `docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md` | This file |

**Files NOT touched (per scope constraint):**
- `packages/research/relevance_filter/svm_training.py` — Prompt A owns this
- `packages/research/relevance_filter/svm_scorer.py` — Prompt A owns this
- `tools/cli/research_acquire.py` — no changes
- `tools/cli/research_prefetch_discover.py` — no changes
- Any L2/L4/Marker IPC code

---

## CLI Design

### Args

| Flag | Default | Notes |
|------|---------|-------|
| `--labels` | `artifacts/research/svm_filter_labels/labels.jsonl` | Read-only; format unchanged |
| `--output-dir` | `artifacts/research/svm_filter_models` | Passed to core |
| `--embedding-cache-dir` | `artifacts/research/svm_filter_embeddings` | Passed to core |
| `--model-name` | `allenai/specter2` | SPECTER2 via sentence-transformers |
| `--random-state` | `42` | Fixed seed for determinism |
| `--test-size` | `0.25` | Train/test split fraction |
| `--json` | off | JSON output mode |
| `--dry-run` | off | Validate labels/deps/core without training |

### Error handling

1. Missing ML deps (`scikit-learn`, `sentence-transformers`) → exit 1, clear install message
2. Labels file not found → exit 1, path in message
3. Insufficient labels (< 5 per class) → exit 1, counts shown
4. Core module not importable (`svm_training.py` absent) → exit 1, no raw traceback
5. `train_and_evaluate_svm` raises at runtime → exit 2, exception message
6. All error paths: no raw Python tracebacks exposed to the operator

### Dry-run behavior

Validates: ML deps installed → labels file exists and has ≥5 per class → core module importable.
Does NOT: call `train_and_evaluate_svm`, write any files, load model weights.

### Expected core API (Prompt A contract)

```python
from packages.research.relevance_filter.svm_training import SvmTrainingConfig, train_and_evaluate_svm

config = SvmTrainingConfig(
    labels_path=Path(...),
    output_dir=Path(...),
    embedding_cache_dir=Path(...),
    model_name="allenai/specter2",
    random_state=42,
    test_size=0.25,
)
result = train_and_evaluate_svm(config)

# result attributes:
# result.metrics           dict (precision/recall/f1 per class + macro_f1)
# result.confusion_matrix  list[list[int]]
# result.model_artifact_path  str | None
# result.metadata_path     str | None
# result.label_count       int
# result.allow_count       int
# result.reject_count      int
# result.random_state      int
```

---

## Commands Run and Output

```
python -m polytool research-prefetch-svm-train --help
```
→ prints full usage, all 8 flags visible, exits 0. ✓

```
python -m pytest tests/test_ris_prefetch_svm_train_cli.py -q --tb=short
```
→ 35 passed in 1.23s ✓

```
python -m pytest tests/test_ris_research_acquire_cli.py -q --tb=short
```
→ 32 passed in 0.90s ✓ (no regressions in existing acquire CLI tests)

---

## Test Results

| Test class | Count | Result |
|-----------|-------|--------|
| `TestHelpFlag` | 1 | PASS |
| `TestMissingMlDeps` | 4 | PASS |
| `TestMissingCoreModule` | 2 | PASS |
| `TestLabelsNotFound` | 1 | PASS |
| `TestInsufficientLabels` | 2 | PASS |
| `TestDryRun` | 6 | PASS |
| `TestFullTrainingPath` | 9 | PASS |
| `TestDefaultArgs` | 3 | PASS |
| `TestCommandRegistration` | 3 | PASS |
| `TestNoSideEffectsOnExistingCLIs` | 3 | PASS |
| **Total** | **35** | **35 PASS / 0 FAIL** |

All tests use `monkeypatch` — no model weights downloaded, no sklearn calls made,
no real artifacts written. `tmp_path` used for all filesystem fixtures.

---

## Interface Notes (Prompt A)

The CLI builds `SvmTrainingConfig` as a class with keyword-argument constructor:
```python
SvmTrainingConfig(
    labels_path=..., output_dir=..., embedding_cache_dir=...,
    model_name=..., random_state=..., test_size=...
)
```

If Prompt A uses a dataclass, this call pattern works. If it uses positional args only,
Prompt A will need to accept the keyword form shown above (standard for dataclasses).

The CLI reads `result.model_artifact_path` and `result.metadata_path` with `if ... else None`
guards, so either `None` or a Path/str is safe.

---

## Open Questions for Integration Prompt

1. **Does `SvmTrainingConfig` use keyword-only args?** The CLI calls it with all
   kwargs; if Prompt A's implementation requires positional args, the CLI call needs
   updating.

2. **Dataclass vs plain class?** If `SvmTrainingConfig` is a dataclass, the call
   pattern works as-is. If it's a plain class with a custom `__init__`, confirm the
   parameter names match those in the CLI.

3. **`result.metrics` shape?** The CLI iterates `result.metrics.items()` for
   human-readable output. The expected shape is `{"precision_allow": float, ...}`.
   If Prompt A uses nested dicts (e.g., `{"per_class": {...}, "macro": {...}}`), the
   human-readable output will need a formatting update.

4. **`result.confusion_matrix`** - the CLI serializes it directly to JSON. If Prompt A
   returns a numpy array rather than a nested list, JSON serialization will fail unless
   the core converts it to a list first (or the CLI adds `.tolist()` conversion).

5. **Default model name** — CLI defaults to `allenai/specter2`. If Prompt A hardcodes
   a different default or uses a different model ID (e.g., `allenai/specter2_base`),
   the CLI `--model-name` default should be updated to match.

---

## Integration Status

- CLI: **done** — `python -m polytool research-prefetch-svm-train --help` works
- Core module (`svm_training.py`): **Prompt A pending**
- SVM scoring wired into pipeline: **not yet** — default-off by design
- `research-acquire` filter modes: **unchanged**
- `research-prefetch-discover` behavior: **unchanged**
