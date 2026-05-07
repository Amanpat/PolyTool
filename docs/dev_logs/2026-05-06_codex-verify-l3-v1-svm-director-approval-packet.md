# Codex Verify - L3 v1 SVM Director Approval Packet

Date: 2026-05-06
Track: Research Intelligence System - L3 v1 SVM Topic Filter
Scope: Review only. No code changes, no training, no label edits, no artifact edits, no feature docs or INDEX edits. This session changed only this review dev log.

## Verdict

FAIL - not ready for Director review/signoff as written.

The underlying expanded 156-label evidence matches the verified artifacts, and SVM enforce remains blocked. The packet should be fixed before Director signoff because its decision/next-action language inaccurately describes SVM dry-run/hold-review as something still needing to be unlocked, and it uses the wrong SVM flag name for `research-prefetch-discover`.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-expanded-156.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-train-eval.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-docs-decision.md`
- `artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json`
- `tools/cli/research_acquire.py` (read-only inspection)
- `tools/cli/research_prefetch_discover.py` (read-only inspection)
- `packages/research/relevance_filter/scorer.py` (read-only inspection)
- `packages/research/relevance_filter/__init__.py` (read-only inspection)
- `polytool/__main__.py` (read-only inspection)
- `docs/INDEX.md` (read-only check for SVM feature-doc/index changes)

## Review Findings

Blocking:

1. The packet states SVM is available via `--prefetch-filter-scorer svm` on both `research-acquire` and `research-prefetch-discover`. That is inaccurate. `research-acquire` uses `--prefetch-filter-scorer`; `research-prefetch-discover` uses `--filter-scorer`.

2. The packet's Decision 2 / Option 1 and next-action table say to unlock dry-run/hold-review and remove a dry-run/hold-review guard. Current code does not hard-block SVM dry-run or hold-review when a model path is provided. Only `research-acquire` SVM `enforce` is hard-blocked with rc=1. The packet should say Option 1 requires no enforce unlock and no removal of a dry-run/hold-review guard; it is a decision to keep evidence collection default-off/score-only while enforcement remains blocked.

Non-blocking / evidence limitation:

- The current worktree is dirty from the broader L3/SVM stream and includes implementation files, tests, and untracked SVM files. The approval packet's "No other files changed" claim is credible only as a session-scoped statement for the packet-writing session; `git diff --stat` cannot verify a repo-wide docs-only tree. No `docs/features/*svm*` file or `docs/INDEX.md` change for the SVM v1 closeout was present in this review.

## Evidence Checks

PASS: default-off integration is correctly described at the high level: lexical remains the default scorer, SVM requires explicit flags, and no default behavior changes were observed in help/code inspection.

PASS: enforce remains blocked. The explicit command below returned rc=1 before any fetch/ingest path.

PASS: expanded evidence matches verified run:

- Labels: 156 total, 74 allow, 82 reject, 3 pending
- Train/test: 117 / 39
- Accuracy: 1.000
- Macro-F1: 1.000
- Confusion matrix: `[[19,0],[0,20]]`
- Metadata path: `artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json`
- Model path: `artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib`

PASS with note: model and metadata artifacts are correctly under `expanded_156`. The embedding cache is correctly referenced as a shared cache under `artifacts/research/svm_filter_models/embeddings/`, not under `expanded_156`.

PASS: caveats are honest. The packet explicitly calls out the small 39-sample eval set, possible topic leakage, unchanged model size, and unresolved SPECTER2 vs validated BGE path.

PASS: options require explicit Director decision. The packet includes a reply template and does not mark an option as approved. It does label Option A and Option 1 as recommended, but does not silently approve them.

PASS: closeout remains blocked. The packet explicitly says not to create the feature doc, not to update closeout state, and not to remove the enforce guard without explicit Director approval recorded in `docs/CURRENT_DEVELOPMENT.md`.

## Commands Run

### git status --short

Exit code: 0. Initial dirty tree before this review:

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/relevance_filter/__init__.py
 M packages/research/relevance_filter/scorer.py
 M polytool/__main__.py
 M pyproject.toml
 M tests/test_ris_prefetch_discovery.py
 M tests/test_ris_research_acquire_cli.py
 M tools/cli/research_acquire.py
 M tools/cli/research_prefetch_discover.py
?? docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-default-off-integration.md
?? docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-train-cli.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-applied-labels.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-cli-fix.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-default-off-fixes.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-doc-cleanup-label-queue.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-expanded-156.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-label-batches-fixed.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-label-batches.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-smoke-and-docs.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-workpacket-blockers.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-acquire-fail-closed.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-label-batch-b-id.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-smoke-doc-caveats.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-workpacket-blockers.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-apply-verified-labels.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-docs-decision.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-train-eval.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-integrated-enforce-blocked-docs.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-label-batch-a.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-label-batch-b.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-label-expansion-queue.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-real-artifact-smoke.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-runtime-scorer.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-train-cli.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-train-eval-readiness-decision.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-training-core.md
?? packages/research/relevance_filter/svm_scorer.py
?? packages/research/relevance_filter/svm_training.py
?? tests/test_ris_prefetch_svm_scorer.py
?? tests/test_ris_prefetch_svm_train.py
?? tests/test_ris_prefetch_svm_train_cli.py
?? tools/cli/research_prefetch_svm_train.py
```

### git log --oneline -5

Exit code: 0.

```text
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

### python -m polytool --help

Exit code: 0. CLI loaded successfully and listed `research-prefetch-svm-train`.

### python -m polytool research-prefetch-review counts --json

Exit code: 0.

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

### git diff --stat

Exit code: 0.

```text
 docs/CURRENT_DEVELOPMENT.md                        |  27 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 218 ++++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 540 +++++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  78 +++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 265 ++++++++--
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  14 +-
 packages/research/relevance_filter/__init__.py     |  12 +-
 packages/research/relevance_filter/scorer.py       |   6 +
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 tests/test_ris_prefetch_discovery.py               | 216 +++++++++
 tests/test_ris_research_acquire_cli.py             | 318 ++++++++++++
 tools/cli/research_acquire.py                      | 140 +++++-
 tools/cli/research_prefetch_discover.py            |  72 ++-
 15 files changed, 1856 insertions(+), 81 deletions(-)
```

PowerShell also printed CRLF warnings for several working-copy files.

### rg file search

Exit code: 1.

```text
Program 'rg.exe' failed to run: Access is denied
```

Fallback PowerShell search commands were used.

### Get-ChildItem docs/dev_logs -Filter *l3-v1-svm-director-approval-packet*.md

Exit code: 0.

```text
D:\Coding Projects\Polymarket\PolyTool\docs\dev_logs\2026-05-06_l3-v1-svm-director-approval-packet.md
```

### Get-ChildItem artifacts/research/svm_filter_models/expanded_156

Exit code: 0.

```text
Name                                        Length LastWriteTime
----                                        ------ -------------
svm_metadata_BAAI_bge-large-en-v1.5_42.json   1182 5/6/2026 1:28:40 PM
svm_model_BAAI_bge-large-en-v1.5_42.joblib   33997 5/6/2026 1:28:40 PM
```

### Get-Content artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json

Exit code: 0. Key fields:

```json
{
  "label_count": 156,
  "allow_count": 74,
  "reject_count": 82,
  "train_size": 117,
  "eval_size": 39,
  "seed": 42,
  "sklearn_version": "1.8.0",
  "model_type": "LinearSVC",
  "embedding_model": "BAAI/bge-large-en-v1.5",
  "metrics": {
    "accuracy": 1.0,
    "precision": {"allow": 1.0, "reject": 1.0, "macro": 1.0},
    "recall": {"allow": 1.0, "reject": 1.0, "macro": 1.0},
    "f1": {"allow": 1.0, "reject": 1.0, "macro": 1.0},
    "train_size": 117,
    "test_size": 39
  },
  "confusion_matrix": [[19, 0], [0, 20]],
  "lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate",
  "skipped_training": false,
  "skip_reason": ""
}
```

### python -m polytool research-acquire --help

Exit code: 0. Relevant result:

- `--prefetch-filter-mode {off,dry-run,enforce,hold-review}` is present.
- `--prefetch-filter-scorer {lexical,svm}` is present.
- Help says lexical is the production default and SVM enforce is blocked pending label gate and Director approval.

### python -m polytool research-prefetch-discover --help

Exit code: 0. Relevant result:

- `--filter-scorer {lexical,svm}` is present.
- There is no `--prefetch-filter-scorer` flag on this command.
- `--svm-model PATH` is required when `--filter-scorer svm`.

### python -m polytool research-acquire ... --prefetch-filter-mode enforce ...

Command:

```powershell
python -m polytool research-acquire --source-family academic --url https://example.com --prefetch-filter-scorer svm --prefetch-filter-mode enforce --prefetch-svm-model artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

Exit code: 1.

```text
Error: SVM enforce is blocked until >=150 labels and Director approval. Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
```

### Get-FileHash artifacts/research/svm_filter_labels/labels.jsonl -Algorithm SHA256

Exit code: 0.

```text
56CEBCC2210BA7FF1A47BA1CB6A64DE649472833D23FB9D3EB4E38BEC387767E
```

### git status --short docs/features docs/INDEX.md artifacts/research/svm_filter_labels/labels.jsonl artifacts/research/svm_filter_models/expanded_156

Exit code: 0. No output.

### Get-ChildItem docs/features -Filter '*svm*'

Exit code: 0. No output.

### Select-String -Path docs/INDEX.md -Pattern "SVM|svm|L3 v1"

Exit code: 0. Existing L3.2 references only; no L3 v1 SVM feature closeout entry was added.

## Required Fixes

1. In the packet Current State table, replace the combined flag claim with:
   - `research-acquire`: `--prefetch-filter-scorer svm`
   - `research-prefetch-discover`: `--filter-scorer svm`

2. Rewrite Decision 2 / Option 1 so it does not say dry-run/hold-review need to be unlocked. Suggested meaning: approve continued default-off score-only/dry-run/hold-review evidence collection with no auto-reject and no removal of the enforce guard.

3. Rewrite the "What changes in code" and "What Happens Next" rows for Option 1. Current code already permits SVM dry-run/hold-review with an explicit model path; the enforce rc=1 guard should stay.

4. Clarify the "No other files changed" statement as session-scoped, because the broader worktree contains pre-existing L3/SVM implementation changes.

## Director Review Status

Director can review the evidence after the packet is corrected. Director should not sign off on the packet as-is because the decision path for Option 1 is technically inaccurate.

## Codex Review Summary

Tier: Skip. This was a docs/artifact verification task, not a code review over live-trading or risk paths.

Issues found: two blocking packet-language inaccuracies, one non-blocking dirty-worktree evidence limitation.

Issues addressed: none; per prompt, this session did not edit the approval packet.
