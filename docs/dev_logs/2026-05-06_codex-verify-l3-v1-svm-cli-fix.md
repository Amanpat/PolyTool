# Codex Verification - L3 v1 SVM Train CLI Fix

Date: 2026-05-06
Reviewer: Codex
Scope: Verification only. No code changes made. This dev log is the only file edit.

## Verdict

PASS.

All four prior Codex findings from `docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md` are resolved by the current workspace state.

Real local train/eval is safe to run next from the CLI/core contract perspective. The real run will instantiate `SentenceTransformer("allenai/specter2")`; if those model weights are not already cached locally, the operator should expect a first-run model download or pre-cache the model before running in an offline environment.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md`
- `docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md`
- `packages/research/relevance_filter/svm_training.py`
- `tools/cli/research_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train_cli.py`
- `polytool/__main__.py`
- `pyproject.toml`
- `tools/cli/research_acquire.py`
- `tools/cli/research_prefetch_discover.py`
- `packages/research/relevance_filter/scorer.py`
- `packages/research/relevance_filter/queue_store.py`

## Prior Findings

### P1: CLI/core config contract mismatch

Resolved.

- `tools/cli/research_prefetch_svm_train.py` constructs `SvmTrainingConfig(label_path=labels_path, ...)`.
- `packages/research/relevance_filter/svm_training.py` defines `SvmTrainingConfig.label_path`.
- `tests/test_ris_prefetch_svm_train_cli.py` now includes real-core signature tests:
  - `test_label_path_kwarg_accepted`
  - `test_labels_path_kwarg_rejected`
  - `test_config_signature_has_label_path_not_labels_path`
- The requested real config construction command exits 0.

### P1: CLI output omits lexical baseline comparison note

Resolved.

- JSON output includes `lexical_baseline_note`.
- Human-readable output prints `baseline        : {result.lexical_baseline_note}`.
- CLI tests assert the JSON and human-readable outputs include `5.88` / `Scenario B`.
- Core metadata also includes `Lexical v1.1 Scenario B: 5.88% off-topic rate`.

### P2: joblib missing-dependency handling incomplete

Resolved.

- `_check_ml_deps()` checks `joblib` alongside `sklearn` and `sentence_transformers`.
- CLI missing-dependency tests include `test_missing_joblib_returns_1`.
- Core lazy import has a separate `joblib` block and raises `SvmMissingDepsError` naming `joblib`.

### P3: default embedding cache path drift

Resolved.

- Default cache dir is `_DEFAULT_OUTPUT_DIR / "embeddings"`.
- Help output shows `artifacts/research/svm_filter_models/embeddings`.
- Dry-run JSON reports `D:\Coding Projects\Polymarket\PolyTool\artifacts\research\svm_filter_models\embeddings`.

## Scope Checks

- No acquisition/discovery SVM enforcement added: PASS. `research_acquire` has no SVM enforcement reference. `research_prefetch_discover` still only reports SVM trigger label counts and uses existing lexical scoring.
- No L2/L4/Marker IPC work added: PASS. Reviewed changed SVM train/core/test surface and adjacent acquisition/discovery/queue files; no Marker IPC or L2/L4 implementation was introduced.
- No label migration: PASS. Label code remains read-only for train/eval; `LabelStore` remains the existing append-only label store.
- Tests avoid network/model downloads: PASS. Core tests inject fake embedding providers. CLI tests monkeypatch ML deps and fake the core module. The real dry-run imports deps only; it does not instantiate `SentenceTransformer` or write artifacts.

## Commands Run

```
git status --short
```

Output:

```
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M polytool/__main__.py
 M pyproject.toml
?? docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-training-core.md
?? packages/research/relevance_filter/svm_training.py
?? tests/test_ris_prefetch_svm_train.py
?? tests/test_ris_prefetch_svm_train_cli.py
?? tools/cli/research_prefetch_svm_train.py
```

```
git log --oneline -5
```

Output:

```
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

```
python -m polytool --help
```

Result: exit 0. Output includes:

```
research-prefetch-svm-train L3 v1 SVM topic filter: train + eval on labeled examples (default-off)
```

```
rg --files -g CLAUDE.md -g AGENTS.md -g docs/CURRENT_DEVELOPMENT.md -g docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md -g packages/research/relevance_filter/svm_training.py -g tools/cli/research_prefetch_svm_train.py -g tests/test_ris_prefetch_svm_train.py -g tests/test_ris_prefetch_svm_train_cli.py
```

Output:

```
Program 'rg.exe' failed to run: Access is denied
```

Fallback PowerShell file reads/searches were used.

```
rg --files docs/dev_logs -g *fix-l3-v1-svm-train-cli-review*.md
```

Output:

```
Program 'rg.exe' failed to run: Access is denied
```

Fallback confirmed:

```
docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
```

```
python -m pytest tests/test_ris_prefetch_svm_train.py -q
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 39 items

tests\test_ris_prefetch_svm_train.py ................................... [ 89%]
....                                                                     [100%]

============================= 39 passed in 2.40s ==============================
```

```
python -m pytest tests/test_ris_prefetch_svm_train_cli.py -q
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 42 items

tests\test_ris_prefetch_svm_train_cli.py ............................... [ 73%]
...........                                                              [100%]

============================= 42 passed in 1.01s ==============================
```

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_prefetch_discovery.py -q
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 131 items

tests\test_ris_relevance_filter.py ..................................... [ 28%]
................                                                         [ 40%]
tests\test_ris_research_acquire_cli.py ................................  [ 64%]
tests\test_ris_prefetch_discovery.py ................................... [ 91%]
...........                                                              [100%]

============================= 131 passed in 1.74s =============================
```

```
python -m polytool research-prefetch-svm-train --help
```

Output:

```
usage: research-prefetch-svm-train [-h] [--labels PATH] [--output-dir PATH]
                                   [--embedding-cache-dir PATH]
                                   [--model-name NAME] [--random-state INT]
                                   [--test-size FLOAT] [--json] [--dry-run]

L3 v1 SVM topic filter: train and evaluate a scikit-learn SVM classifier on
labeled prefetch filter examples using SPECTER2/S2FOS embeddings. Integration
is default-off - this command trains and exports the model artifact; it does
not activate SVM scoring in the live pipeline.

options:
  -h, --help            show this help message and exit
  --labels PATH         Labels JSONL file path (default:
                        artifacts/research/svm_filter_labels/labels.jsonl).
  --output-dir PATH     Directory for trained model artifacts (default:
                        artifacts/research/svm_filter_models).
  --embedding-cache-dir PATH
                        Directory for cached embeddings; cached embeddings are
                        re-used on subsequent runs to avoid re-embedding the
                        same candidates (default:
                        artifacts/research/svm_filter_models/embeddings).
  --model-name NAME     sentence-transformers embedding model name (default:
                        allenai/specter2). Model weights are loaded from local
                        cache or downloaded once by the operator; they are NOT
                        downloaded on every invocation.
  --random-state INT    Random seed for train/test split and SVM classifier
                        (default: 42). Two runs on the same labels.jsonl with
                        the same seed produce identical metrics.
  --test-size FLOAT     Fraction of labels held out for evaluation (default:
                        0.25).
  --json                Output structured JSON result instead of human-
                        readable text.
  --dry-run             Validate labels, check ML dependencies, and verify the
                        core module is importable - without loading model
                        weights or writing artifacts.
```

PowerShell equivalent of the requested `python - <<'PY'` command:

```
@'
from pathlib import Path
from packages.research.relevance_filter.svm_training import SvmTrainingConfig
cfg = SvmTrainingConfig(
    label_path=Path("artifacts/research/svm_filter_labels/labels.jsonl"),
    output_dir=Path("artifacts/research/svm_filter_models"),
    embedding_cache_dir=Path("artifacts/research/svm_filter_models/embeddings"),
    model_name="allenai/specter2",
)
print(cfg)
'@ | python -
```

Output:

```
SvmTrainingConfig(label_path=WindowsPath('artifacts/research/svm_filter_labels/labels.jsonl'), output_dir=WindowsPath('artifacts/research/svm_filter_models'), embedding_cache_dir=WindowsPath('artifacts/research/svm_filter_models/embeddings'), model_name='allenai/specter2', random_state=42, test_size=0.25, min_per_class=5)
```

Additional non-training dry-run:

```
python -m polytool research-prefetch-svm-train --dry-run --json
```

Output:

```
{
  "dry_run": true,
  "labels_path": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_labels\\labels.jsonl",
  "label_count": 61,
  "allow_count": 30,
  "reject_count": 31,
  "model_name": "allenai/specter2",
  "random_state": 42,
  "test_size": 0.25,
  "output_dir": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_models",
  "embedding_cache_dir": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_models\\embeddings",
  "deps_ok": true,
  "core_module_ok": true,
  "ready_to_train": true
}
```

## Decisions

- PASS the fix verification.
- Treat real local train/eval as safe to run next, with the model-cache caveat above.
- Keep acquisition/discovery SVM enforcement blocked/default-off until a real eval artifact is reviewed.

## Open Questions / Blockers

None for this verification.

## Codex Review Summary

Review tier: Recommended. This is RIS filtering/training CLI/core verification; no live trading, risk, execution, rate limiter, kill-switch, or order-placement code was touched.

Issues found in this verification: none.

Issues addressed in this verification: none; review-only task.
