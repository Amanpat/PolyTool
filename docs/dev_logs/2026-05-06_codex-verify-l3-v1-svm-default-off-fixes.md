# Codex Verify - L3 v1 SVM Default-Off Fixes

Date: 2026-05-06
Reviewer: Codex
Scope: Review only. No implementation code, labels, model artifacts, L2/L4 code, or Marker IPC code changed.

## Verdict

PASS.

The failed L3 v1 SVM default-off integration review blockers are resolved enough to declare explicit SVM dry-run / hold-review evidence collection safe.

Default remains lexical. SVM remains opt-in. SVM enforce remains blocked until at least 150 labels and Director approval. The current label store is still 61 labels: 30 allow, 31 reject, 1 pending unlabeled.

## Prior P1 Disposition

1. P1: `research-prefetch-discover` did not preserve SVM audit fields in queued/dry-run records.
   - Resolved.
   - `tools/cli/research_prefetch_discover.py` now copies `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, and `svm_lexical_baseline_note` into the discovery record before either `--dry-run --json` emits `would_queue` or normal mode writes to the review queue.
   - `tests/test_ris_prefetch_discovery.py` now covers SVM dry-run records, SVM queued records, and lexical records with empty SVM fields.

2. P1: explicit SVM score-time failures in `research-acquire` could fail open as unfiltered acquisition.
   - Resolved for `research-acquire`.
   - `_score_candidate_for_filter()` returns before SVM imports in mode `off`; active SVM modes propagate score/load/dependency errors.
   - `main()` and `_run_search_mode()` now return rc=1 with a clear "SVM scoring failed ... aborting to prevent unfiltered acquisition" error on SVM score-time failures.
   - `tests/test_ris_research_acquire_cli.py` covers hold-review model-load failure, dry-run score failure, and off mode never invoking the scorer.

Residual note: `research-prefetch-discover` still calls `scorer.score(candidate)` outside a formatted score-time error handler. A missing/corrupt SVM model would fail stop rather than queue unfiltered evidence, so this is not a remaining safety blocker for evidence collection, but a future UX cleanup could turn the traceback into a formatted rc=1 CLI error.

## Review Findings

- Discovery audit fields: PASS.
- Acquire explicit SVM score-time fail-closed behavior: PASS.
- SVM mode off does not import/load/fail on SVM in acquire: PASS.
- Lexical remains the default scorer and acquire mode remains `off`: PASS.
- SVM enforce remains blocked pending >=150 labels and Director approval: PASS.
- Tests do not download model weights: PASS. Runtime scorer tests use small sklearn/joblib fixtures and injected embedding providers. Train CLI tests monkeypatch the SVM module/dependency checks and write temporary labels under `tmp_path`.
- Labels were not modified: PASS. SHA256 before and after requested commands stayed `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`.
- No L2/L4/Marker IPC work occurred: PASS. The implementation diff is limited to RIS SVM/default-off docs, CLI, relevance-filter package/tests, `pyproject.toml`, and `polytool/__main__.py`; no Marker IPC, L2, or L4 implementation files appeared in the reviewed diff/status.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/dev_logs/2026-05-06_codex-review-l3-v1-svm-default-off-integration.md`
- `docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md`
- `docs/dev_logs/2026-05-06_fix-l3-v1-svm-acquire-fail-closed.md`
- `tools/cli/research_prefetch_discover.py`
- `tools/cli/research_acquire.py`
- `tools/cli/research_prefetch_svm_train.py`
- `packages/research/relevance_filter/scorer.py`
- `packages/research/relevance_filter/svm_scorer.py`
- `packages/research/relevance_filter/svm_training.py`
- `packages/research/relevance_filter/__init__.py`
- `polytool/__main__.py`
- `pyproject.toml`
- `tests/test_ris_prefetch_discovery.py`
- `tests/test_ris_research_acquire_cli.py`
- `tests/test_ris_prefetch_svm_scorer.py`
- `tests/test_ris_relevance_filter.py`
- `tests/test_ris_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train_cli.py`

## Commands Run

Session start checks:

```text
git status --short
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
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-acquire-fail-closed.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md
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
Exit code 0. CLI loaded and listed research-acquire, research-prefetch-discover, research-prefetch-review, and research-prefetch-svm-train.
```

Requested verification commands:

```text
python -m pytest tests/test_ris_prefetch_discovery.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 52 items

tests\test_ris_prefetch_discovery.py ................................... [ 67%]
.................                                                        [100%]

============================= 52 passed in 0.82s ==============================
```

```text
python -m pytest tests/test_ris_research_acquire_cli.py -q
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 42 items

tests\test_ris_research_acquire_cli.py ................................. [ 78%]
.........                                                                [100%]

============================= 42 passed in 1.06s ==============================
```

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

============================= 42 passed in 2.21s ==============================
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

============================= 134 passed in 4.33s =============================
```

```text
python -m polytool research-acquire --help
Exit code 0.
Relevant output:
  --prefetch-filter-mode {off,dry-run,enforce,hold-review}
  --prefetch-filter-scorer {lexical,svm}
                        Relevance filter scorer backend (default: lexical).
                        lexical: keyword-based v1.1 scorer (production
                        default). svm: trained SVM model - requires
                        --prefetch-svm-model; enforce mode is blocked for SVM
                        until >=150 labels and Director approval.
  --prefetch-svm-model PATH
                        Path to trained SVM .joblib model artifact (required
                        when --prefetch-filter-scorer svm and mode is not
                        off).
```

```text
python -m polytool research-prefetch-discover --help
Exit code 0.
Relevant output:
  L3.2 Prefetch Label Discovery: search arXiv metadata only, score candidates
  with the relevance filter, and enqueue to the prefetch review queue. No PDFs
  are downloaded. No ingestion, no Marker. (Lexical mode: no embeddings. SVM
  mode --filter-scorer svm: uses embedding model.)
  --filter-scorer {lexical,svm}
                        Relevance filter scorer backend (default: lexical).
                        svm: use trained SVM model - requires --svm-model.
  --svm-model PATH      Path to trained SVM .joblib model artifact (required
                        when --filter-scorer svm).
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
 docs/CURRENT_DEVELOPMENT.md                        |  28 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  20 +-
 .../.smart-env/event_logs/event_logs.ajson         |  82 +++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 190 ++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  33 +++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 195 +++++++++++--
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  11 +-
 packages/research/relevance_filter/__init__.py     |  12 +-
 packages/research/relevance_filter/scorer.py       |   6 +
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 tests/test_ris_prefetch_discovery.py               | 216 ++++++++++++++
 tests/test_ris_research_acquire_cli.py             | 318 +++++++++++++++++++++
 tools/cli/research_acquire.py                      | 140 +++++++--
 tools/cli/research_prefetch_discover.py            |  72 ++++-
 15 files changed, 1254 insertions(+), 78 deletions(-)
```

Label hash before requested commands:

```text
Get-FileHash -Algorithm SHA256 -LiteralPath artifacts/research/svm_filter_labels/labels.jsonl
SHA256 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

Label hash after requested commands:

```text
Get-FileHash -Algorithm SHA256 -LiteralPath artifacts/research/svm_filter_labels/labels.jsonl
SHA256 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

Additional read-only note:

```text
rg -n ...
Program 'rg.exe' failed to run: Access is denied.
Fallback used: Select-String over the requested files.
```

## Decisions

- PASS the SVM default-off integration fixes for explicit evidence collection.
- Treat SVM enforcement as still blocked. The current corpus is below the requested 150-label enforcement floor and the help text explicitly requires Director approval.
- Do not request any implementation changes in this review pass.

## Open Questions / Blockers

- None blocking for explicit SVM dry-run / hold-review evidence collection.
- Future cleanup: format `research-prefetch-discover` score-time SVM load/dependency failures as a clean rc=1 CLI error instead of relying on fail-stop traceback behavior.

## Codex Review Summary

Tier: Recommended review. Scope is RIS CLI/relevance-filter integration and tests; no live trading, order placement, kill-switch, risk manager, L2, L4, or Marker IPC code.

Issues found: no remaining blocking issue for explicit evidence collection.

Issues addressed by this session: none; review/dev-log only by instruction.
