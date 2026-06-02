---
title: Codex Review L3 V1 Svm Default Off Integration
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-default-off-integration.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - L3 v1 SVM Default-Off Integration

Date: 2026-05-06
Reviewer: Codex
Scope: Review only. No implementation code changed. This file is the only edit made by this session.

## Verdict

FAIL.

Lexical remains the default and the requested test suites pass, but the SVM integration is not yet safe enough to declare explicit dry-run / hold-review evidence collection complete across both CLI paths.

Blocking review findings:

1. `research-prefetch-discover` does not preserve SVM audit fields in queued or dry-run records. The queue record is built from `FilterDecision` fields at `tools/cli/research_prefetch_discover.py:416`, but it omits `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, and `svm_lexical_baseline_note`. SVM-discovered evidence therefore cannot be reliably tied back to the scorer/model that produced it.
2. SVM score-time load/dependency failures are not handled consistently at the CLI boundary. `research-acquire` catches all scoring failures at `tools/cli/research_acquire.py:79`, warns, returns `None`, and then proceeds as if no filter decision existed. In explicit SVM hold-review mode this can bypass the intended hold-review evidence path if the model, metadata, or optional deps are missing. `research-prefetch-discover` catches scorer initialization, but SVM loading is lazy and happens at `scorer.score(...)` on `tools/cli/research_prefetch_discover.py:409`, outside the initialization try block.

Non-blocking note:

- `research-prefetch-discover --help` still says "No ingestion, no embeddings, no Marker." That remains true for lexical mode, but SVM mode does create embeddings through the runtime scorer. The help text should be made conditional or less absolute.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-runtime-scorer.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md`
- `packages/research/relevance_filter/svm_scorer.py`
- `packages/research/relevance_filter/scorer.py`
- `packages/research/relevance_filter/__init__.py`
- `packages/research/relevance_filter/queue_store.py`
- `tools/cli/research_acquire.py`
- `tools/cli/research_prefetch_discover.py`
- `tests/test_ris_prefetch_svm_scorer.py`
- `tests/test_ris_research_acquire_cli.py`
- `tests/test_ris_prefetch_discovery.py`
- `tests/test_ris_relevance_filter.py`
- `tests/test_ris_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train_cli.py`

## Verification Checklist

1. Lexical scorer remains default everywhere: PASS.
   - `research-acquire`: `--prefetch-filter-mode` defaults to `off`; `--prefetch-filter-scorer` defaults to `lexical`.
   - `research-prefetch-discover`: `--filter-scorer` defaults to `lexical`.
2. SVM requires explicit scorer/model flags and is not loaded in mode `off`: PASS for explicit gating.
   - `research-acquire` permits `scorer=svm` with mode `off` and no model; `_score_candidate_for_filter` returns before SVM import/load.
   - Active SVM modes require `--prefetch-svm-model`.
   - `research-prefetch-discover` has no `off` mode, and requires `--svm-model` when `--filter-scorer svm`.
3. SVM dry-run/hold-review paths work and preserve audit fields: FAIL.
   - `research-acquire` preserves SVM audit fields in `filter_decisions.jsonl`.
   - `research-prefetch-discover` queues/would-queue records without SVM audit fields.
4. SVM enforce is blocked with clear message until >=150 labels and Director approval: PASS.
   - `research-acquire` returns rc=1 for `--prefetch-filter-mode enforce --prefetch-filter-scorer svm`.
5. Runtime scorer handles missing model/metadata/deps gracefully: PARTIAL.
   - `SvmRelevanceScorer` raises domain errors with clear messages for missing model, missing metadata, corrupt artifacts, missing `joblib`, missing `numpy`, and missing `sentence-transformers`.
   - CLI handling is not sufficient: acquire can bypass explicit SVM filtering on score failure, and discover can raise at score time outside the scorer-init try block.
6. Tests do not download model weights: PASS.
   - Runtime tests use tiny sklearn fixtures and injected embedding providers.
   - Train CLI tests monkeypatch the core module and dependency checks.
7. No labels were modified: PASS.
   - `artifacts/research/svm_filter_labels/labels.jsonl` SHA256 before and after read-only commands: `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`.
8. No L2/L4/Marker IPC work occurred: PASS.
   - Diffed files are docs, RIS relevance filter modules, RIS CLIs, tests, `pyproject.toml`, and `polytool/__main__.py`. No L2, L4, or Marker IPC implementation files were changed.
9. No production claim was added: PASS.
   - The reviewed integration keeps lexical as the production default and states SVM enforce is blocked.

## Commands Run

Session start checks:

```text
git status --short
Exit code 0.
Output showed existing dirty/untracked L3 SVM implementation files and prior dev logs. No files were reverted or overwritten.
```

```text
git log --oneline -5
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

```text
python -m polytool --help
Exit code 0.
CLI loaded successfully and listed research-prefetch-svm-train, research-prefetch-discover, research-prefetch-review, and research-acquire.
```

Requested verification commands:

```text
python -m pytest tests/test_ris_prefetch_svm_scorer.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 42 items

tests\test_ris_prefetch_svm_scorer.py .................................. [ 80%]
........                                                                 [100%]

============================= 42 passed in 1.82s ==============================
```

```text
python -m pytest tests/test_ris_research_acquire_cli.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 39 items

tests\test_ris_research_acquire_cli.py ................................. [ 84%]
......                                                                   [100%]

============================= 39 passed in 0.81s ==============================
```

```text
python -m pytest tests/test_ris_prefetch_discovery.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 49 items

tests\test_ris_prefetch_discovery.py ................................... [ 71%]
..............                                                           [100%]

============================= 49 passed in 0.58s ==============================
```

```text
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 134 items

tests\test_ris_relevance_filter.py ..................................... [ 27%]
................                                                         [ 39%]
tests\test_ris_prefetch_svm_train.py ................................... [ 65%]
....                                                                     [ 68%]
tests\test_ris_prefetch_svm_train_cli.py ............................... [ 91%]
...........                                                              [100%]

============================= 134 passed in 3.83s =============================
```

```text
python -m polytool research-acquire --help
Exit code 0.
Relevant output:
  --prefetch-filter-mode {off,dry-run,enforce,hold-review}
  --prefetch-filter-scorer {lexical,svm}
      Relevance filter scorer backend (default: lexical).
      lexical: keyword-based v1.1 scorer (production default).
      svm: trained SVM model - requires --prefetch-svm-model;
      enforce mode is blocked for SVM until >=150 labels and Director approval.
  --prefetch-svm-model PATH
  --prefetch-svm-metadata PATH
```

```text
python -m polytool research-prefetch-discover --help
Exit code 0.
Relevant output:
  --filter-scorer {lexical,svm}
      Relevance filter scorer backend (default: lexical).
      svm: use trained SVM model - requires --svm-model.
  --svm-model PATH
  --svm-metadata PATH
```

```text
python -m polytool research-prefetch-review counts --json
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

```text
git diff --stat
 docs/CURRENT_DEVELOPMENT.md                        |  28 ++-
 docs/obsidian-vault/.obsidian/workspace.json       |  20 +-
 .../.smart-env/event_logs/event_logs.ajson         |  82 +++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 190 ++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  33 ++++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 195 +++++++++++++++---
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  11 +-
 packages/research/relevance_filter/__init__.py     |  12 +-
 packages/research/relevance_filter/scorer.py       |   6 +
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 tests/test_ris_prefetch_discovery.py               |  83 ++++++++
 tests/test_ris_research_acquire_cli.py             | 218 +++++++++++++++++++++
 tools/cli/research_acquire.py                      |  81 +++++++-
 tools/cli/research_prefetch_discover.py            |  61 +++++-
 15 files changed, 968 insertions(+), 61 deletions(-)
```

Additional read-only checks:

```text
Get-FileHash -Algorithm SHA256 -LiteralPath artifacts/research/svm_filter_labels/labels.jsonl
SHA256 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

The same hash was observed before and after the requested command set.

## Fixes Required

1. Add SVM audit fields to `research-prefetch-discover` queue and dry-run records when `FilterDecision.scorer == "svm"`, and add assertions in `tests/test_ris_prefetch_discovery.py`.
2. Make explicit SVM scoring failures fail closed at the CLI boundary with a clear rc=1 message. Do not let `research-acquire` proceed as unfiltered in active SVM modes when model, metadata, or deps are missing. Catch score-time SVM load/dependency errors in `research-prefetch-discover`.
3. Update `research-prefetch-discover` help text so SVM mode is not described as "no embeddings."

## Codex Review Summary

Tier: Recommended review. Files are RIS relevance filter runtime, CLI wiring, and tests; no execution, live trading, kill-switch, risk manager, or order placement code.

Issues found: two blocking review findings and one non-blocking help-text issue.

Issues addressed: none in this session by instruction. Implementation code was not edited.

