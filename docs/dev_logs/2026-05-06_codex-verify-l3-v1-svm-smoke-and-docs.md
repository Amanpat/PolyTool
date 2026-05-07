# Codex Verify - L3 v1 SVM Smoke and Docs

Date: 2026-05-06
Reviewer: Codex
Scope: Verification only. No code, labels, model artifacts, or existing docs were edited. This review dev log is the only file created by this session.

## Verdict

PASS for the narrow integration status: L3 v1 SVM can be considered default-off integrated and enforce-blocked.

Closeout is not allowed yet. Label expansion should happen first unless the Director explicitly chooses to close the feature at dry-run/hold-review capability only.

## Smoke Artifacts Reviewed

- `artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib`
- `artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json`
- `artifacts/research/svm_filter_smoke/filter_decisions.jsonl`
- `artifacts/research/svm_filter_smoke/discovery_dry_run.json`
- `docs/dev_logs/2026-05-06_l3-v1-svm-real-artifact-smoke.md`
- `docs/dev_logs/2026-05-06_l3-v1-svm-integrated-enforce-blocked-docs.md`

Artifact inspection showed a real saved joblib model exists, not just a fake scorer fixture:

```text
Directory: D:\Coding Projects\Polymarket\PolyTool\artifacts\research\svm_filter_models

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
d-----          5/6/2026   8:52 AM                embeddings
-a----          5/6/2026   8:55 AM           1317 first-real-train-eval.json
-a----          5/6/2026   8:53 AM           1177 svm_metadata_BAAI_bge-large-en-v1.5_42.json
-a----          5/6/2026   8:53 AM          33997 svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

Metadata key fields:

```json
{
  "label_count": 61,
  "allow_count": 30,
  "reject_count": 31,
  "train_size": 45,
  "eval_size": 16,
  "seed": 42,
  "sklearn_version": "1.8.0",
  "model_type": "LinearSVC",
  "embedding_model": "BAAI/bge-large-en-v1.5",
  "metrics": {
    "accuracy": 1.0,
    "f1": {
      "macro": 1.0
    }
  },
  "lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate",
  "skipped_training": false
}
```

The runtime scorer loads the saved model via `joblib.load(model_path)` and reads metadata JSON at score time. The smoke output records an absolute `svm_model_path` pointing at the saved joblib artifact.

## Review Findings

1. Real-artifact smoke: PASS.
   - The model and metadata files exist under `artifacts/research/svm_filter_models/`.
   - Smoke records reference the real saved model path.
   - Runtime code loads the joblib artifact and metadata; tests use fake providers, but the smoke artifacts are not fake test fixtures.

2. SVM scorer/model audit evidence: PASS.
   - `research-prefetch-discover --dry-run` smoke output includes `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, and `svm_lexical_baseline_note` on all 5 records.
   - `research-acquire` smoke audit includes `scorer`, `svm_model_name`, and `svm_model_path`; it does not include the random-state/baseline-note fields, but the prompt allowed dry-run and/or hold-review evidence, and discovery dry-run covers the full audit set.

3. Enforce blocked: PASS.
   - Direct command returned exit code 1 with: `Error: SVM enforce is blocked until >=150 labels and Director approval. Use --prefetch-filter-mode dry-run or hold-review for evidence collection.`
   - No fetch or ingest was needed for that failure.

4. Lexical remains default: PASS.
   - `research-acquire --help` shows `--prefetch-filter-scorer {lexical,svm}` with `default: lexical`.
   - `research-prefetch-discover --help` shows `--filter-scorer {lexical,svm}` with `default: lexical`.
   - Code inspection confirms both argparse defaults are `lexical`.

5. Labels were not modified: PASS.
   - Counts remain `30 allow / 31 reject / 1 pending unlabeled`.
   - `labels.jsonl` SHA256 remains `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`.

6. Docs match evidence and avoid production-readiness claims: PARTIAL.
   - The main status docs correctly say default-off, smoke PASS, enforce blocked, and not production-ready.
   - Required doc cleanup remains:
     - `docs/CURRENT_DEVELOPMENT.md` still says `peft` is not in `pyproject.toml` and must be added, while a later note says `peft` was added in the integration commit. Current `pyproject.toml` does not include `peft` in `ris-svm`, so those docs conflict.
     - The work packet DoD checkboxes for train/eval, labels read-only, cache reuse, evaluation report, metadata ledger, and graceful failure remain unchecked even though `CURRENT_DEVELOPMENT.md` marks them complete.
     - The docs should avoid implying a live hold-review real-artifact smoke completed; the real smoke completed acquire/discover dry-run evidence, while live hold-review was blocked by arXiv 429 and covered by tests/queue-path evidence.

7. No L2/L4/Marker IPC work occurred: PASS.
   - `git diff --stat` tracked changes are RIS SVM scorer/CLI/test/docs/pyproject related.
   - Untracked files are SVM modules/tests/dev logs.
   - L2/L4/Marker references found in docs are status/deferred-dependency text, not implementation work.

8. Next step: label expansion first.
   - Current label count is 61; enforce gate requires >=150 labels plus Director approval.
   - Closeout docs should wait until label expansion/model-selection decisions are resolved, or until the Director explicitly chooses a dry-run/hold-review-only closeout.

## Commands Run

### `git status --short`

Exit code: 0

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
?? docs/dev_logs/2026-05-06_codex-verify-l3-v1-svm-real-train-eval.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-acquire-fail-closed.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md
?? docs/dev_logs/2026-05-06_fix-l3-v1-svm-train-cli-review.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md
?? docs/dev_logs/2026-05-06_l3-v1-svm-integrated-enforce-blocked-docs.md
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

### `git log --oneline -5`

Exit code: 0

```text
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers — Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation — L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
```

### `python -m polytool --help`

Exit code: 0

Result: CLI loaded successfully. It listed `research-acquire`, `research-prefetch-discover`, `research-prefetch-review`, and `research-prefetch-svm-train`.

### `python -m polytool research-prefetch-review counts --json`

Exit code: 0

```json
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

### `python -m pytest tests/test_ris_research_acquire_cli.py tests/test_ris_prefetch_discovery.py tests/test_ris_prefetch_svm_scorer.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 136 items

tests\test_ris_research_acquire_cli.py ................................. [ 24%]
.........                                                                [ 30%]
tests\test_ris_prefetch_discovery.py ................................... [ 56%]
.................                                                        [ 69%]
tests\test_ris_prefetch_svm_scorer.py .................................. [ 94%]
........                                                                 [100%]

============================= 136 passed in 3.19s =============================
```

### `python -m polytool research-acquire --help`

Exit code: 0

```text
usage: research-acquire [-h] [--url URL | --search QUERY] [--max-results N]
                        [--source-family FAMILY] [--cache-dir PATH]
                        [--review-dir PATH] [--db PATH] [--no-eval]
                        [--dry-run] [--json] [--provider NAME]
                        [--priority-tier TIER] [--extract-claims]
                        [--run-log PATH]
                        [--prefetch-filter-mode {off,dry-run,enforce,hold-review}]
                        [--prefetch-filter-config PATH]
                        [--prefetch-review-queue-dir PATH]
                        [--prefetch-filter-scorer {lexical,svm}]
                        [--prefetch-svm-model PATH]
                        [--prefetch-svm-metadata PATH]

Fetch a source from a URL and ingest it into the RIS knowledge store.

options:
  -h, --help            show this help message and exit
  --url URL             Source URL to fetch.
  --search QUERY        ArXiv topic search query (academic family only).
                        Fetches up to --max-results papers and ingests each
                        one.
  --max-results N       Maximum number of results for --search (default: 5).
  --source-family FAMILY
                        Source family: academic, github, blog, news, book,
                        reddit, or youtube (required).
  --cache-dir PATH      Directory for raw-source cache (default:
                        artifacts/research/raw_source_cache).
  --review-dir PATH     Directory for acquisition review JSONL (default:
                        artifacts/research/acquisition_reviews).
  --db PATH             Custom knowledge store path (default: system default).
  --no-eval             Skip evaluation gate (hard-stop checks still run).
  --dry-run             Fetch and normalize only; do not cache, ingest, or
                        write review.
  --json                Output JSON to stdout.
  --provider NAME       Evaluation provider (default: manual).
  --priority-tier TIER  Priority tier for gate thresholds (default: config
                        default, usually priority_3). priority_1 applies lower
                        threshold (trusted sources); priority_4 applies higher
                        threshold (low-trust sources).
  --extract-claims      Run claim extraction after ingest (opt-in; non-fatal
                        if extraction fails).
  --run-log PATH        Path to run log JSONL for health tracking (default:
                        artifacts/research/run_log.jsonl).
  --prefetch-filter-mode {off,dry-run,enforce,hold-review}
                        Relevance pre-fetch filter mode (default: off). dry-
                        run: score and log but always ingest. enforce: skip
                        REJECT; ingest REVIEW with audit flag. hold-review:
                        ingest ALLOW only; skip REJECT; queue REVIEW without
                        ingesting.
  --prefetch-filter-config PATH
                        Path to relevance filter config JSON (default: auto-
                        discover config/research_relevance_filter_v1.json).
  --prefetch-review-queue-dir PATH
                        Directory for the hold-review JSONL queue (default:
                        artifacts/research/prefetch_review_queue).
  --prefetch-filter-scorer {lexical,svm}
                        Relevance filter scorer backend (default: lexical).
                        lexical: keyword-based v1.1 scorer (production
                        default). svm: trained SVM model — requires
                        --prefetch-svm-model; enforce mode is blocked for SVM
                        until >=150 labels and Director approval.
  --prefetch-svm-model PATH
                        Path to trained SVM .joblib model artifact (required
                        when --prefetch-filter-scorer svm and mode is not
                        off).
  --prefetch-svm-metadata PATH
                        Path to SVM metadata JSON (optional; inferred from
                        model path when omitted).
```

### `python -m polytool research-prefetch-discover --help`

Exit code: 0

```text
usage: research-prefetch-discover [-h] --search QUERY [--source-family FAMILY]
                                  [--max-results N] [--include-allow]
                                  [--decision-filter DECISIONS] [--force]
                                  [--queue-path PATH] [--label-path PATH]
                                  [--filter-config PATH] [--timeout SECONDS]
                                  [--json] [--dry-run]
                                  [--filter-scorer {lexical,svm}]
                                  [--svm-model PATH] [--svm-metadata PATH]

L3.2 Prefetch Label Discovery: search arXiv metadata only, score candidates
with the relevance filter, and enqueue to the prefetch review queue. No PDFs
are downloaded. No ingestion, no Marker. (Lexical mode: no embeddings. SVM
mode --filter-scorer svm: uses embedding model.)

options:
  -h, --help            show this help message and exit
  --search QUERY        arXiv search query string.
  --source-family FAMILY
                        Source family to search (only 'academic'/arXiv
                        supported in v0). Default: academic.
  --max-results N, --limit N
                        Maximum number of search results to fetch. Default:
                        20.
  --include-allow       Also queue ALLOW candidates (for positive label
                        accumulation). Default: queue REVIEW candidates only.
  --decision-filter DECISIONS
                        Comma-separated decisions to queue:
                        allow,review,reject,all. Overrides --include-allow.
                        Default: review.
  --force               Re-queue candidates already in the queue (override
                        idempotency). Creates a new entry for the same URL.
  --queue-path PATH     Override review queue JSONL path.
  --label-path PATH     Override label store JSONL path.
  --filter-config PATH  Override relevance filter config JSON path.
  --timeout SECONDS     HTTP timeout for arXiv API call. Default: 15.
  --json                Output structured JSON summary instead of human-
                        readable text.
  --dry-run             Score and show what would be queued without writing
                        anything.
  --filter-scorer {lexical,svm}
                        Relevance filter scorer backend (default: lexical).
                        svm: use trained SVM model — requires --svm-model.
  --svm-model PATH      Path to trained SVM .joblib model artifact (required
                        when --filter-scorer svm).
  --svm-metadata PATH   Path to SVM metadata JSON (optional; inferred from
                        model path when omitted).
```

### `git diff --stat`

Exit code: 0

```text
 docs/CURRENT_DEVELOPMENT.md                        |  28 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 122 +++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 289 +++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  51 ++++
 ...ork-Packet - L3 v1 SVM Topic Filter Training.md | 207 ++++++++++++--
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  12 +-
 packages/research/relevance_filter/__init__.py     |  12 +-
 packages/research/relevance_filter/scorer.py       |   6 +
 polytool/__main__.py                               |   3 +
 pyproject.toml                                     |   6 +
 tests/test_ris_prefetch_discovery.py               | 216 ++++++++++++++
 tests/test_ris_research_acquire_cli.py             | 318 +++++++++++++++++++++
 tools/cli/research_acquire.py                      | 140 +++++++--
 tools/cli/research_prefetch_discover.py            |  72 ++++-
 15 files changed, 1425 insertions(+), 79 deletions(-)
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

### Direct enforce-block check

Command:

```text
python -m polytool research-acquire --url https://arxiv.org/abs/1802.06101 --source-family academic --prefetch-filter-mode enforce --prefetch-filter-scorer svm --prefetch-svm-model artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

Exit code: 1

```text
Error: SVM enforce is blocked until >=150 labels and Director approval. Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
```

### Label hash check

Command:

```text
Get-FileHash artifacts/research/svm_filter_labels/labels.jsonl -Algorithm SHA256
```

Exit code: 0

```text
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2       D:\Coding Projects\Polymarket...
```

### Code inspection notes

`rg` was attempted first per repo convention, but failed in this sandbox with `Access is denied`. I used PowerShell `Select-String` and targeted `Get-Content` ranges as fallback.

Relevant code facts inspected:

- `packages/research/relevance_filter/svm_scorer.py` lazily loads the saved model via `joblib.load(model_path)`.
- `tools/cli/research_acquire.py` defaults `--prefetch-filter-scorer` to `lexical`.
- `tools/cli/research_acquire.py` blocks `scorer=svm + mode=enforce` before URL/search validation.
- `tools/cli/research_prefetch_discover.py` defaults `--filter-scorer` to `lexical`.
- `tools/cli/research_prefetch_discover.py` writes SVM audit fields into discovery records.
- `packages/research/relevance_filter/scorer.py` defaults `FilterDecision.scorer` to `lexical` with empty SVM fields.

## Fixes Required

1. Correct the `peft` docs conflict.
   - Current evidence: `pyproject.toml` has `ris-svm = ["scikit-learn>=1.3.0", "sentence-transformers>=2.2.0", "joblib>=1.3.0"]`; no `peft`.
   - Docs should either keep `peft` as an unresolved dependency blocker or remove the claim that it was added.

2. Align the work packet DoD checkboxes with the evidence.
   - `CURRENT_DEVELOPMENT.md` marks several train/eval and metadata DoD items complete.
   - The work packet still leaves those same items unchecked.

3. Tighten wording around hold-review real-artifact smoke.
   - Evidence supports real-artifact dry-run and test-backed hold-review queue behavior.
   - The live hold-review smoke itself was not completed because arXiv returned HTTP 429.

4. Continue label expansion before enforcement/closeout.
   - Current labels: 61 total, 30 allow, 31 reject.
   - Enforcement gate remains >=150 labels plus Director approval.

## Codex Review Summary

Tier: Recommended verification review. Files under review are RIS SVM runtime/CLI/tests/docs; no live trading, execution, kill-switch, risk manager, or order-placement code was touched.

Issues found: no implementation blocker for default-off integrated/enforce-blocked status. Docs cleanup is required before closeout.

Issues addressed: none by instruction. This session created only this review dev log.
