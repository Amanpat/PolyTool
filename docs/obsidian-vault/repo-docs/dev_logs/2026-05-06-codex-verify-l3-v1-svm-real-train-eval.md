---
title: Codex Verify L3 V1 Svm Real Train Eval
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify - L3 v1 SVM Real Train/Eval Evidence

**Date:** 2026-05-06
**Scope:** Review-only verification of the first real L3 v1 SVM train/eval evidence and readiness decision.
**Verdict:** PASS - safe to prompt default-off SVM integration next.

## Files Changed

Only this review dev log was created:

- `docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md` - records verification findings and command outputs.

No implementation code, labels, generated model artifacts, prior docs, L2/L4 code, or Marker IPC files were modified by this review.

## Evidence Reviewed

- `docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-train-eval-readiness-decision.md`
- `artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json`
- `artifacts/research/svm_filter_models/first-real-train-eval.json`
- `artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib`
- `artifacts/research/svm_filter_models/embeddings/`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md`

## Findings

PASS: Real train/eval actually ran. The evidence is not dry-run only:

- Model artifact exists: `artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib` (33,997 bytes).
- Model metadata exists: `artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json` (1,177 bytes).
- Run-summary artifact exists: `artifacts/research/svm_filter_models/first-real-train-eval.json` (1,317 bytes).
- Embedding cache contains 61 JSON vectors.
- Metadata has `"skipped_training": false`.

PASS: Artifact evidence includes the requested fields:

- Label counts: 61 total, 30 allow, 31 reject.
- Deterministic seed: model metadata uses `"seed": 42`; CLI/run summary uses `"random_state": 42`.
- Model name: `BAAI/bge-large-en-v1.5` in `embedding_model` and `model_used`.
- Classifier: `LinearSVC`.
- Metrics: accuracy, precision, recall, F1, train/test sizes.
- Confusion matrix: `[[8, 0], [0, 8]]`.
- Baseline note: `Lexical v1.1 Scenario B: 5.88% off-topic rate`.
- Artifact paths: `first-real-train-eval.json` records `model_artifact_path` and `metadata_path`.

PASS: Metrics are reported honestly with caveats. The docs repeatedly state that the 16-sample holdout is not statistically conclusive and should not be used as proof of production generalization. They also require label-corpus expansion before enforce mode.

PASS: Docs decision matches the evidence. `CURRENT_DEVELOPMENT.md`, `Current-Focus.md`, and the work packet all record `PROCEED` only for default-off integration, with open caveats for model selection, `peft`, and corpus expansion.

PASS: No acquisition/discovery integration was implemented yet. The worktree changes only register the train/eval CLI, add the optional `ris-svm` dependency group/package include, and add standalone SVM training files/tests. `research_acquire.py`, `research_prefetch_discover.py`, and `packages/research/relevance_filter/scorer.py` are not modified. A search for SVM references in acquisition/discovery/scorer files found only the existing L3.2 SVM label-count trigger in `research_prefetch_discover.py`, not SVM scoring integration.

PASS: No labels were modified during this review. `labels.jsonl` SHA-256 was identical before and after the requested dry-run/tests:

`3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

PASS: No L2, L4, or Marker IPC work occurred in the reviewed changes. `git diff --name-only` contains no L2/L4/Marker IPC paths, and untracked files are limited to SVM train/eval code, tests, and dev logs.

## Metrics Summary

- Labels: 61 total; 30 allow; 31 reject.
- Split: 45 train; 16 eval; stratified; seed/random_state 42.
- Embedding model used: `BAAI/bge-large-en-v1.5`.
- Intended/default model: `allenai/specter2`, currently blocked by AdapterHub/PEFT mismatch.
- Classifier: `LinearSVC`.
- Accuracy: 1.000.
- Precision macro: 1.000.
- Recall macro: 1.000.
- F1 macro: 1.000.
- Confusion matrix: `[[8, 0], [0, 8]]`.
- Baseline note: lexical v1.1 Scenario B at 5.88% off-topic.
- Caveat: 16 eval examples is too small for enforcement confidence.

## Decision

PASS: Default-off SVM integration may be prompted next.

No blocker prevents the next integration prompt if it stays default-off and keeps existing modes unchanged. The integration prompt should explicitly resolve model selection and dependency handling, and it must not enable production enforcement.

Blocking before enforce/production, not before default-off integration:

- Choose production embedding model: SPECTER2 path vs `BAAI/bge-large-en-v1.5`.
- Add any required optional dependency (`peft` and/or AdapterHub-compatible `adapters`) once model choice is made.
- Expand labels well beyond 61 examples before using SVM enforcement; current docs suggest 150+.

## Commands Run

### `git status --short`

```text
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
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-cli-fix.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-train-eval-readiness-decision.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-training-core.md
?? packages/research/relevance_filter/svm_training.py
?? tests/test_ris_prefetch_svm_train.py
?? tests/test_ris_prefetch_svm_train_cli.py
?? tools/cli/research_prefetch_svm_train.py
```

### `git log --oneline -5`

```text
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

### `python -m polytool --help`

Exit code 0. Relevant line present:

```text
  research-prefetch-svm-train L3 v1 SVM topic filter: train + eval on labeled examples (default-off)
```

### `rg --files ...`

Attempted first per repo convention. `rg.exe` failed to launch:

```text
Program 'rg.exe' failed to run: Access is denied
```

Fallback used PowerShell `Get-ChildItem` and `Select-String`.

### `python -m polytool research-prefetch-review counts --json`

```text
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

### `python -m polytool research-prefetch-svm-train --dry-run --json`

```text
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

### `python -m pytest tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py -q`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 81 items

tests\test_ris_prefetch_svm_train.py ................................... [ 43%]
....                                                                     [ 48%]
tests\test_ris_prefetch_svm_train_cli.py ............................... [ 86%]
...........                                                              [100%]

============================= 81 passed in 3.49s ==============================
```

### `git diff --stat`

```text
 docs/CURRENT_DEVELOPMENT.md                        |  28 ++-
 docs/obsidian-vault/.obsidian/workspace.json       |  20 +--
 .../.smart-env/event_logs/event_logs.ajson         |  82 ++++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 190 ++++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  33 ++++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 195 ++++++++++++++++++---
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  11 +-
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 9 files changed, 526 insertions(+), 42 deletions(-)
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md', LF will be replaced by CRLF the next time Git touches it
```

### `Get-ChildItem -Path artifacts\research\svm_filter_models\embeddings -Recurse -File | Measure-Object`

```text
Count    : 61
Average  :
Sum      :
Maximum  :
Minimum  :
Property :
```

### `Get-FileHash artifacts\research\svm_filter_labels\labels.jsonl -Algorithm SHA256`

Before and after verification commands:

```text
SHA256 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

## Codex Review Summary

Review tier: Recommended/read-only verification for RIS filtering/training evidence; no live trading, execution, risk manager, rate limiter, or kill-switch code.

Issues found: none blocking default-off integration prompt.

Issues carried forward: model selection, optional dependency declaration, and label-corpus expansion before any enforcement.
