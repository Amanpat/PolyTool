---
title: Codex Review L3 V1 Svm Train Cli
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - L3 v1 SVM Train CLI

Date: 2026-05-06
Reviewer: Codex
Scope: Review only. No code changes made. This dev log is the only file edit.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-training-core.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md`
- `packages/research/relevance_filter/svm_training.py`
- `tools/cli/research_prefetch_svm_train.py`
- `polytool/__main__.py`
- `pyproject.toml`
- `tests/test_ris_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train_cli.py`
- `tools/cli/research_acquire.py`
- `tools/cli/research_prefetch_discover.py`
- `packages/research/relevance_filter/scorer.py`
- `packages/research/relevance_filter/queue_store.py`

## Verdict

FAIL.

The implementation stays within Feature 3 scope and does not wire SVM into production acquisition/discovery enforcement, but the combined CLI + core is not safe to proceed to real local train/eval yet. The non-dry-run CLI constructs `SvmTrainingConfig(labels_path=...)`, while the real core dataclass accepts `label_path`. The requested tests pass because the CLI tests use a fake core module with the CLI's incorrect constructor signature.

Acquisition/discovery integration should remain blocked. SVM scoring is not active today, and it should remain default-off until the CLI/core contract and reporting blockers below are fixed.

## Findings

### Blocking: CLI/core config contract mismatch

File: `tools/cli/research_prefetch_svm_train.py`
Lines: 287-294

The CLI passes `labels_path=labels_path` into `SvmTrainingConfig`, but `packages/research/relevance_filter/svm_training.py` defines the dataclass field as `label_path`. A real non-dry-run CLI invocation will fail before training starts:

```
TypeError: SvmTrainingConfig.__init__() got an unexpected keyword argument 'labels_path'
```

Suggested fix:

- Change the CLI keyword to `label_path=labels_path`, or rename the core dataclass field to `labels_path` consistently.
- Add a test that imports the real `SvmTrainingConfig` signature instead of only testing against the fake CLI test module.

### Blocking: CLI output omits lexical baseline comparison note

File: `tools/cli/research_prefetch_svm_train.py`
Lines: 303-341

The core result and metadata include the lexical v1.1 Scenario B 5.88% note, but the CLI JSON and human-readable output omit it. The work packet acceptance criteria require the evaluation report to include the lexical v1.1 Scenario B 5.88% comparison.

Suggested fix:

- Include `lexical_baseline_note` in JSON output.
- Print the same note in human-readable output.
- Add CLI tests asserting `5.88` or `Scenario B` appears in output.

### Non-blocking but required before closeout: joblib dep check is incomplete

File: `tools/cli/research_prefetch_svm_train.py`
Lines: 44-59

The CLI checks `sklearn` and `sentence_transformers`, but not `joblib`, even though the core imports `joblib` and `pyproject.toml` adds it to `[ris-svm]`. If joblib is missing from a broken environment, the failure is caught later as a generic training failure and the core message says scikit-learn is required, which is not specific enough for the requested graceful dependency behavior.

Suggested fix:

- Add `joblib` to `_check_ml_deps()`.
- Add CLI and core missing-joblib tests.
- Make the core error message name the missing package or split the lazy imports into clearer dependency checks.

### Non-blocking: embedding cache default path does not match packet

File: `tools/cli/research_prefetch_svm_train.py`
Lines: 35-38

The work packet says embedding cache should live under `artifacts/research/svm_filter_models/embeddings/`, but the CLI default is `artifacts/research/svm_filter_embeddings`. This does not break training, but it creates artifact layout drift.

Suggested fix:

- Change `_DEFAULT_EMBEDDING_CACHE_DIR` to `_DEFAULT_OUTPUT_DIR / "embeddings"` and update help/tests/dev log text.

## Scope Checks

- Feature 3 only: PASS. Reviewed code changes are SVM train/eval core, CLI registration, optional deps, and tests.
- No L2/L4/Marker IPC work: PASS. Search of `polytool`, `tools`, and `packages` found no new SVM references outside command registration/core/CLI and existing SVM label-count readiness text.
- Labels JSONL read-only/no migration: PASS. Core reads via `_read_jsonl`; CLI reads JSONL for validation only. No label writer or migration is introduced.
- SVM production enforcement/acquisition: PASS. `research_acquire` modes remain `off`, `dry-run`, `enforce`, `hold-review`; no `svm` mode is added. `research_prefetch_discover` still uses lexical `RelevanceScorer` and label-count readiness only.
- CLI and core API match: FAIL. `labels_path` vs `label_path`.
- Missing sklearn/joblib/sentence-transformers graceful failure: PARTIAL. sklearn and sentence-transformers are covered; joblib is not checked explicitly.
- Tests avoid model downloads/network: PASS by inspection. Core tests inject fake embeddings; CLI tests monkeypatch deps/core.
- `random_state=42` determinism and artifact metadata/ledger: PASS by inspection and tests. Core uses `train_test_split(... random_state=config.random_state, stratify=y)` and `LinearSVC(random_state=config.random_state)`, and writes required metadata fields.
- Metrics include precision, recall, F1, confusion matrix, counts, lexical Scenario B note: PARTIAL. Core metrics/metadata include them, but CLI output omits the lexical note.

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

Output: exited 0. The command list includes `research-prefetch-svm-train L3 v1 SVM topic filter: train + eval on labeled examples (default-off)`.

```
rg --files docs/dev_logs -g "*l3-v1-svm-training-core*.md" -g "*l3-v1-svm-train-cli*.md"
```

Output:

```
Program 'rg.exe' failed to run: Access is denied
```

Fallback used:

```
Get-ChildItem -Path docs/dev_logs -Filter "*l3-v1-svm-training-core*.md" | Select-Object -ExpandProperty FullName
Get-ChildItem -Path docs/dev_logs -Filter "*l3-v1-svm-train-cli*.md" | Select-Object -ExpandProperty FullName
```

Output:

```
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-06_l3-v1-svm-training-core.md
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-06_l3-v1-svm-train-cli.md
```

```
python -m pytest tests/test_ris_prefetch_svm_train.py -q
```

Output:

```
collected 39 items
tests\test_ris_prefetch_svm_train.py ................................... [ 89%]
....                                                                     [100%]
39 passed in 2.79s
```

```
python -m pytest tests/test_ris_prefetch_svm_train_cli.py -q
```

Output:

```
collected 35 items
tests\test_ris_prefetch_svm_train_cli.py ............................... [ 88%]
....                                                                     [100%]
35 passed in 1.07s
```

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_prefetch_discovery.py -q
```

Output:

```
collected 131 items
tests\test_ris_relevance_filter.py ..................................... [ 28%]
................                                                         [ 40%]
tests\test_ris_research_acquire_cli.py ................................  [ 64%]
tests\test_ris_prefetch_discovery.py ................................... [ 91%]
...........                                                              [100%]
131 passed in 1.98s
```

```
python -m polytool research-prefetch-review counts --json
```

Output:

```
{
  "total_queued": 62,
  "pending_unlabeled": 1,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31,
  "pending_review_count": 62,
  "label_count": 61,
  "allowed_label_count": 30,
  "rejected_label_count": 31
}
```

```
python -m polytool research-prefetch-svm-train --help
```

Output: exited 0. Usage shows all expected flags: `--labels`, `--output-dir`, `--embedding-cache-dir`, `--model-name`, `--random-state`, `--test-size`, `--json`, `--dry-run`.

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
  "embedding_cache_dir": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_embeddings",
  "deps_ok": true,
  "core_module_ok": true,
  "ready_to_train": true
}
```

```
python -c "import inspect; from packages.research.relevance_filter.svm_training import SvmTrainingConfig; print(inspect.signature(SvmTrainingConfig))"
```

Output:

```
(label_path: 'Path', output_dir: 'Path', embedding_cache_dir: 'Path', model_name: 'str', random_state: 'int' = 42, test_size: 'float' = 0.25, min_per_class: 'int' = 5) -> None
```

```
python -c "from pathlib import Path; from packages.research.relevance_filter.svm_training import SvmTrainingConfig; SvmTrainingConfig(labels_path=Path('labels.jsonl'), output_dir=Path('out'), embedding_cache_dir=Path('cache'), model_name='allenai/specter2')"
```

Output:

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
TypeError: SvmTrainingConfig.__init__() got an unexpected keyword argument 'labels_path'
```

```
python -c "import importlib.util; print('sklearn', bool(importlib.util.find_spec('sklearn'))); print('joblib', bool(importlib.util.find_spec('joblib'))); print('sentence_transformers', bool(importlib.util.find_spec('sentence_transformers')))"
```

Output:

```
sklearn True
joblib True
sentence_transformers True
```

## Safety Decision

Not safe to proceed to real local train/eval until the CLI/core API mismatch is fixed and the lexical baseline note is exposed in CLI output.

Acquisition/discovery integration should remain blocked. The current code correctly keeps SVM enforcement default-off and inactive, and that should not change until train/eval passes and explicit evaluation gates are met.

## Codex Review Summary

Review tier: Recommended, because this touches RIS filtering/training CLI and core but not live trading, execution, risk, rate limiting, kill-switch, py_clob_client, or order placement.

Issues found: 2 blocking, 2 non-blocking.

Issues addressed: none. Review-only task; no code changes made.
