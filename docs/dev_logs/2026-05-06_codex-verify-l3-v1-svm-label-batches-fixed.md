# Codex Verify - L3 v1 SVM Label Batches A/B Fixed

Date: 2026-05-06
Reviewer: Codex
Scope: Read-only verification of corrected Director label review packets A and B. No labels applied, no code changed, no model artifacts changed, no training run.

## Verdict

PASS. The Director can safely use the corrected packets for manual labeling.

Batch B #82 now uses the full current pending candidate ID:

`c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e`

The malformed `c958d1df01636431` command is gone. Both packet tables resolve against the current 98-item pending queue, Batch A covers sorted positions 1-49, Batch B covers sorted positions 50-98, and all suggested label commands resolve to exactly one current pending queue record.

## Files Changed

Only this review dev log was created:

- `docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-label-batches-fixed.md`

No labels, packet files, implementation code, tests, model artifacts, queue files, or training outputs were edited by this Codex verification.

## Findings

| Check | Result |
|---|---|
| Batch B #82 uses full corrected ID | PASS |
| Malformed `c958d1df01636431` remains | PASS: 0 matches |
| Batch A covers pending candidates 1-49 | PASS |
| Batch B covers pending candidates 50-98 | PASS |
| Duplicate candidate IDs across packet tables | PASS: 0 duplicates |
| Omitted pending candidates | PASS: 0 omissions |
| Extra non-pending candidates | PASS: 0 extras |
| Suggested label commands resolve to current pending records | PASS: 95/95 resolve once |
| `labels.jsonl` modified | PASS: unchanged SHA and older mtime |
| Code/model artifacts modified by the Batch B ID fix | PASS with caveat: current worktree has pre-existing L3 code diffs, but diff stat matches prior verification and model artifact mtimes predate the packet fix |
| Projected `labeled_total` after non-pending recommendations | PASS: 156, which is >=150 |
| Closeout blocked after labeling | PASS: still blocked on label application, retrain/eval, Director approval, model choice, and closeout docs |

## Counts and Projection

Current counts:

| Metric | Value |
|---|---:|
| total_queued | 159 |
| pending_unlabeled | 98 |
| labeled_total | 61 |
| labeled_allow | 30 |
| labeled_reject | 31 |

Recommendation summary:

| Batch | Allow | Reject | Leave pending | Total |
|---|---:|---:|---:|---:|
| A | 21 | 26 | 2 | 49 |
| B | 23 | 25 | 1 | 49 |
| Total | 44 | 51 | 3 | 98 |

If all non-pending recommendations are applied:

- projected labeled_allow: 74
- projected labeled_reject: 82
- projected labeled_total: 156
- projected pending_unlabeled: 3
- reaches >=150: yes

## Important Caveat

`git diff --stat` currently shows pre-existing tracked code/doc/test changes from the broader L3 v1 SVM workstream. This was already present in the earlier verification dev log. The current stat output matches that prior verification output, and the Batch B ID fix dev log records only a packet artifact edit plus its own dev log. Artifact files under `artifacts/` are ignored by git, so the corrected packet itself does not appear in `git diff --stat`.

SVM model artifact mtimes are 08:53-08:55, before the packet/fix work. `labels.jsonl` mtime remains 2026-05-05 14:34:27 and SHA remains unchanged.

## Commands Run and Output

### git status --short

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
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-cli-fix.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-default-off-fixes.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-doc-cleanup-label-queue.md
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
?? docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md
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

```text
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

### python -m polytool --help

Exit code 0. Relevant command present:

```text
research-prefetch-review  List/label L3 hold-review queue items; export label counts for SVM
```

### python -m polytool research-prefetch-review counts --json

```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31,
  "pending_review_count": 159,
  "label_count": 61,
  "allowed_label_count": 30,
  "rejected_label_count": 31
}
```

### Get-FileHash -Algorithm SHA256 -LiteralPath 'artifacts\research\svm_filter_labels\labels.jsonl'

```text
SHA256  3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

This matches the baseline SHA in both packets and the prior verification/fix dev logs.

### git diff --stat

```text
 docs/CURRENT_DEVELOPMENT.md                        |  27 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 160 +++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 410 +++++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  62 ++++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 229 ++++++++++--
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  13 +-
 packages/research/relevance_filter/__init__.py     |  12 +-
 packages/research/relevance_filter/scorer.py       |   6 +
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 tests/test_ris_prefetch_discovery.py               | 216 +++++++++++
 tests/test_ris_research_acquire_cli.py             | 318 ++++++++++++++++
 tools/cli/research_acquire.py                      | 140 +++++--
 tools/cli/research_prefetch_discover.py            |  72 +++-
 15 files changed, 1617 insertions(+), 79 deletions(-)
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'packages/research/relevance_filter/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'packages/research/relevance_filter/scorer.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_ris_prefetch_discovery.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tools/cli/research_prefetch_discover.py', LF will be replaced by CRLF the next time Git touches it
```

### Packet and label file metadata

```json
[
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_label_expansion\\label_batch_A.md",
    "Length": 25324,
    "LastWriteTime": "2026-05-06 11:05:45"
  },
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_label_expansion\\label_batch_B.md",
    "Length": 24469,
    "LastWriteTime": "2026-05-06 12:57:57"
  },
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_labels\\labels.jsonl",
    "Length": 22505,
    "LastWriteTime": "2026-05-05 14:34:27"
  }
]
```

### SVM model artifact metadata

```json
[
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_models\\first-real-train-eval.json",
    "Length": 1317,
    "LastWriteTime": "2026-05-06 08:55:47"
  },
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_models\\svm_metadata_BAAI_bge-large-en-v1.5_42.json",
    "Length": 1177,
    "LastWriteTime": "2026-05-06 08:53:38"
  },
  {
    "FullName": "D:\\Coding Projects\\Polymarket\\PolyTool\\artifacts\\research\\svm_filter_models\\svm_model_BAAI_bge-large-en-v1.5_42.joblib",
    "Length": 33997,
    "LastWriteTime": "2026-05-06 08:53:38"
  }
]
```

### Malformed ID scan

Command:

```powershell
Select-String -LiteralPath 'artifacts\research\svm_filter_label_expansion\label_batch_A.md','artifacts\research\svm_filter_label_expansion\label_batch_B.md' -Pattern 'c958d1df01636431' -SimpleMatch
```

Output:

```text
(no output)
```

### Corrected full ID scan

Command:

```powershell
Select-String -LiteralPath 'artifacts\research\svm_filter_label_expansion\label_batch_B.md' -Pattern 'c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e' -SimpleMatch
```

Output summary:

```text
artifacts\research\svm_filter_label_expansion\label_batch_B.md:98: table row #82 contains the full corrected ID and full corrected label command
artifacts\research\svm_filter_label_expansion\label_batch_B.md:149: Director ALLOW command block contains the full corrected label command
```

### Packet consistency script

Command:

```powershell
# Parsed research-prefetch-review list --json, sorted pending candidates by candidate_id,
# extracted both packet tables and Director command sections, resolved every token
# against the current pending queue, and compared packet coverage to sorted positions.
```

Output:

```json
{
  "pending_count": 98,
  "batch_A": {
    "rows": 49,
    "row_numbers": "1-49",
    "table_token_lengths": [
      15,
      16,
      17
    ],
    "recommendations": {
      "allow": 21,
      "reject": 26,
      "leave_pending": 2,
      "unknown": 0
    },
    "commands": 47,
    "command_labels": {
      "allow": 21,
      "reject": 26
    },
    "command_token_lengths": [
      64
    ],
    "rows_unresolved_or_ambiguous_count": 0,
    "commands_bad_format_count": 0,
    "commands_unresolved_or_ambiguous_count": 0,
    "duplicate_row_candidate_ids_count": 0,
    "matches_expected_sorted_slice": true
  },
  "batch_B": {
    "rows": 49,
    "row_numbers": "50-98",
    "table_token_lengths": [
      16,
      64
    ],
    "recommendations": {
      "allow": 23,
      "reject": 25,
      "leave_pending": 1,
      "unknown": 0
    },
    "commands": 48,
    "command_labels": {
      "allow": 23,
      "reject": 25
    },
    "command_token_lengths": [
      16,
      64
    ],
    "rows_unresolved_or_ambiguous_count": 0,
    "commands_bad_format_count": 0,
    "commands_unresolved_or_ambiguous_count": 0,
    "duplicate_row_candidate_ids_count": 0,
    "matches_expected_sorted_slice": true,
    "corrected_82_rows": 1,
    "corrected_82_commands": 1
  },
  "coverage": {
    "union_count": 98,
    "union_unique_count": 98,
    "duplicate_candidate_ids_across_batches_count": 0,
    "omitted_pending_ids_count": 0,
    "extra_ids_not_pending_count": 0
  },
  "commands_across_batches": {
    "unique_targets": 95,
    "allow": 44,
    "reject": 51,
    "conflicts_count": 0
  },
  "malformed_c958_count": 0,
  "full_c958_match_count_batch_B": 2,
  "projected_labeled_total": 156
}
```

## Decisions Made

- Marked the corrected packets PASS because all packet rows and suggested label commands now resolve against the current pending queue, with no duplicates, omissions, extras, malformed commands, or conflicting command labels.
- Treated Batch A's 15/16/17-character table display prefixes as acceptable because each resolves exactly once and Batch A's actual Director commands use full 64-character IDs.
- Treated Batch B's 16-character command prefixes as acceptable because the CLI help explicitly allows unambiguous prefixes, and the script confirmed each resolves exactly once.
- Did not run training or apply labels because the objective forbids it.

## Open Questions / Blockers

- Labels are still unapplied. Current `labeled_total` remains 61.
- Manual labeling may proceed, but closeout remains blocked until:
  - labels are applied,
  - retrain/eval passes on the enriched corpus,
  - Director approval is given,
  - model choice is resolved,
  - closeout docs are created.

## Codex Review Summary

Tier: artifact review only; no implementation code reviewed or modified.
Issues found: none blocking after the Batch B #82 fix.
Issues addressed: none by Codex in this session; this verification changed only the dev log.
