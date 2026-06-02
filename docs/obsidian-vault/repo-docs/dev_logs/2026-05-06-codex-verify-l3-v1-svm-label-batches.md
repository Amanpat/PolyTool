---
title: Codex Verify L3 V1 Svm Label Batches
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-label-batches.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify - L3 v1 SVM Label Batches A/B

Date: 2026-05-06
Reviewer: Codex
Scope: Read-only verification of Director label review packets A and B. No labels applied, no code changed, no training run.

## Verdict

FAIL. The Director should not apply the packets as-is.

Blocking issue: Batch B candidate #82 uses the malformed prefix `c958d1df01636431` in both the table and suggested command. The current pending queue contains `c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e` for "Model-based gym environments for limit order book trading". The packet typo matches zero pending records and zero all-queue records, so the command would fail and the union covers only 97 of 98 current pending candidates.

## Files Changed

Only this review dev log was created:

- `docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-label-batches.md` - records verification findings and command outputs.

No labels, implementation code, tests, model artifacts, queue files, or batch packet files were edited by this Codex verification.

## Required Checks

1. Both batch files exist: PASS.
2. Batch A and B use the same deterministic split rule: PASS. Both describe sorting pending candidates by `candidate_id` ascending and splitting 1-49 / 50-98.
3. Batch A covers sorted positions 1-49: PASS.
4. Batch B covers sorted positions 50-98: FAIL due to #82 malformed prefix.
5. No duplicate candidate IDs across resolvable rows: PASS.
6. Union covers current pending unlabeled candidates: FAIL. One omission: `c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e`.
7. Recommendations are conservative and include confidence/rationale: PASS. Both tables include confidence and rationale. Leave-pending is used for low-confidence cases.
8. Suggested label commands contain no duplicate/conflicting labels and no dangerous operations: PASS for resolved commands, but FAIL overall because Batch B #82 command has a malformed/non-matching ID.
9. `labels.jsonl` was not modified: PASS. Current SHA matches packet baselines; file last write time is 2026-05-05 14:34:27.
10. No implementation code/model artifacts were modified by the batch prompts: PASS with caveat. The worktree already has implementation code changes from prior L3 work, but the batch dev logs only created packet docs. SVM model artifact mtimes are 08:53-08:55, before Batch B 11:03 and Batch A 11:05.
11. Closeout remains blocked: PASS. Current labeled_total is still 61, labels have not been applied, Batch B has a blocker, and Director approval is still required before any enforcement.

## Counts and Projection

Current counts:

- total_queued: 159
- pending_unlabeled: 98
- labeled_total: 61
- labeled_allow: 30
- labeled_reject: 31

Recommendation summary from rows:

| Batch | Allow | Reject | Leave pending | Total |
|---|---:|---:|---:|---:|
| A | 21 | 26 | 2 | 49 |
| B | 23 | 25 | 1 | 49 |
| Total | 44 | 51 | 3 | 98 |

If the malformed Batch B #82 ID is corrected and all non-pending recommendations are applied:

- projected labeled_allow: 74
- projected labeled_reject: 82
- projected labeled_total: 156
- projected pending_unlabeled: 3
- reaches >=150: yes

If the packets are applied as-is, the #82 command fails; at most 94 labels can be applied automatically, projecting labeled_total to 155 if the operator skips the failing command. That still reaches >=150, but the packet is not safe as-is because the Director requested reliable manual-label packets and exact coverage.

## Required Fix

Fix Batch B candidate #82 in `artifacts/research/svm_filter_label_expansion/label_batch_B.md`:

- replace table prefix `c958d1df01636431` with `c958d1df0163643d`
- replace command `python -m polytool research-prefetch-review label c958d1df01636431 allow` with either:
  - `python -m polytool research-prefetch-review label c958d1df0163643d allow`
  - or the full ID: `python -m polytool research-prefetch-review label c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e allow`

After that fix, rerun the consistency script before Director labeling.

## Command Outputs

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
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-smoke-and-docs.md
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-workpacket-blockers.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-acquire-fail-closed.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md
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

Exit code 0. Relevant command present under RIS:

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

### Get-FileHash artifacts/research/svm_filter_labels/labels.jsonl -Algorithm SHA256

```text
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2       D:\Coding Projects\Polymarket\PolyTool\artifacts\research\svm_filter_labels\labels.jsonl
```

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

### Batch file existence and timestamps

```text
Name          : label_batch_A.md
Length        : 25324
LastWriteTime : 5/6/2026 11:05:45 AM

Name          : label_batch_B.md
Length        : 24325
LastWriteTime : 5/6/2026 11:03:15 AM
```

### Label file timestamp

```text
FullName      : D:\Coding Projects\Polymarket\PolyTool\artifacts\research\svm_filter_labels\labels.jsonl
Length        : 22505
LastWriteTime : 5/5/2026 2:34:27 PM
```

### SVM model artifact timestamps

```text
Name          : first-real-train-eval.json
Length        : 1317
LastWriteTime : 5/6/2026 8:55:47 AM

Name          : svm_metadata_BAAI_bge-large-en-v1.5_42.json
Length        : 1177
LastWriteTime : 5/6/2026 8:53:38 AM

Name          : svm_model_BAAI_bge-large-en-v1.5_42.joblib
Length        : 33997
LastWriteTime : 5/6/2026 8:53:38 AM
```

### CLI label command contract

```text
usage: research-prefetch-review label [-h] [--note NOTE] [--queue-path PATH]
                                      [--label-path PATH] [--json]
                                      CANDIDATE_ID LABEL

positional arguments:
  CANDIDATE_ID       Full candidate_id or unambiguous prefix (from 'list'
                     output).
  LABEL              Label: 'allow' or 'reject'.

options:
  -h, --help         show this help message and exit
  --note NOTE        Optional operator note.
  --queue-path PATH  Override review queue JSONL path.
  --label-path PATH  Override label store JSONL path.
  --json             Output raw JSON instead of human-readable text.
```

### Pending queue around Batch B #82

```text
78: bb81ac9c4c8915a4110cf5993ab98e224106f403a5fa73185125f37a2b8e610c | TradeFM: A Generative Foundation Model for Trade-flow and Market Microstructure
79: c3d38f94c1d1bf9104659ae9c54d8f6c49c39915f440df46d9c591102a50a965 | Active learning for data streams: a survey
80: c45011073a8d28fac073bef52512b57aa10c832cb225fdad1755d48fad1993a7 | Public Policymaking for International Agricultural Trade using Association Rules and Ensemble Machine Learning
81: c838207810d11fadb5a047bd4153d0618bedda119381dd3bb10ecdeda039b92b | Understanding the Impacts of Dark Pools on Price Discovery
82: c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e | Model-based gym environments for limit order book trading
83: c9d32650dad3766badba45d43eca7c02e23745eacdeee7e6214df79f243f70ff | TapNet: Neural Network Augmented with Task-Adaptive Projection for Few-Shot Learning
84: c9fc18e35ccaf41f3662ff831d7f74c5defe80afdf7867d90cffc019cab339e8 | A Benchmark Study of Machine Learning Models for Online Fake News Detection
```

### Batch B typo location

```text
artifacts\research\svm_filter_label_expansion\label_batch_B.md:98:| 82 | `c958d1df01636431` | Model-based gym environments for limit order book trading | 0.9933 | allow | **allow** | high | LOB trading gym environments for RL - directly relevant to backtesting and strategy validation infrastructure in PolyTool. | `python -m polytool research-prefetch-review label c958d1df01636431 allow` |
artifacts\research\svm_filter_label_expansion\label_batch_B.md:149:python -m polytool research-prefetch-review label c958d1df01636431 allow
```

### Consistency script summary

```json
{
  "A": {
    "exists": true,
    "table_rows": 49,
    "row_number_first_last": [
      1,
      49
    ],
    "rows_with_nonunique_or_missing_queue_match": [],
    "duplicate_table_candidate_ids": [],
    "recommendations_from_rows": {
      "allow": 21,
      "reject": 26,
      "leave_pending": 2,
      "unknown": 0
    },
    "label_commands": 47,
    "label_command_counts": {
      "allow": 21,
      "reject": 26
    },
    "label_command_token_lengths": [
      64
    ],
    "commands_with_nonunique_or_missing_queue_match": []
  },
  "B": {
    "exists": true,
    "table_rows": 49,
    "row_number_first_last": [
      50,
      98
    ],
    "rows_with_nonunique_or_missing_queue_match": [
      {
        "n": 82,
        "prefix": "c958d1df01636431",
        "pending_matches": 0,
        "all_matches": 0
      }
    ],
    "duplicate_table_candidate_ids": [],
    "recommendations_from_rows": {
      "allow": 23,
      "reject": 25,
      "leave_pending": 1,
      "unknown": 0
    },
    "label_commands": 48,
    "label_command_counts": {
      "allow": 23,
      "reject": 25
    },
    "label_command_token_lengths": [
      16
    ],
    "commands_with_nonunique_or_missing_queue_match": [
      {
        "token": "c958d1df01636431",
        "label": "allow",
        "pending_matches": 0,
        "all_matches": 0
      }
    ]
  },
  "coverage": {
    "pending_count": 98,
    "batch_A_matches_positions_1_49": true,
    "batch_B_matches_positions_50_98": false,
    "union_count": 97,
    "union_unique_count": 97,
    "duplicate_ids_across_batches": [],
    "omitted_pending_ids": [
      "c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e"
    ],
    "extra_ids_not_pending": [],
    "first_pending_id": "000c6e786a9e56ec29f16a89dd13d1f9c1f4ce409bb895c72484ed98483f2595",
    "split_last_A_id": "8535d25e89c505722b6a7e17dfcec7b95a159c0bfbd1d065576462d66d31716a",
    "split_first_B_id": "86ee8fa78cf400e991bf7da5650b79438a17c0265e3f5a7fb4392f4aa92725a7",
    "last_pending_id": "fb12002203e77b3c6921b2eb9321ec2749c9f12557c7cf7bae480df10f2f4c70"
  },
  "commands_across_batches": {
    "unique_command_targets": 95,
    "allow": 44,
    "reject": 51,
    "duplicate_or_conflicting_labels": []
  }
}
```

### Standalone command safety scan

```text
artifacts\research\svm_filter_label_expansion\label_batch_A.md: malformed_or_dangerous_standalone_commands=0
artifacts\research\svm_filter_label_expansion\label_batch_B.md: malformed_or_dangerous_standalone_commands=0
```

## Decisions Made

- Marked the verification FAIL because the Director asked whether the packets can safely be used for manual labeling. A single malformed command is enough to make the answer no.
- Treated Batch B 16-character prefixes as acceptable in principle because the CLI explicitly allows unambiguous prefixes.
- Did not edit the packet files because the task allowed only the review dev log.

## Open Questions / Blockers

- Batch B #82 needs correction before Director labeling.
- Labels have not been applied; current labeled_total remains 61.
- Even after reaching >=150 projected labels, enforce remains blocked until Director approval and remaining closeout documentation gates are satisfied.

## Codex Review Summary

Tier: artifact review only; no implementation code reviewed or modified.
Issues found: one blocking malformed Batch B candidate ID/label command.
Issues addressed: none, by instruction to change only this review dev log.
