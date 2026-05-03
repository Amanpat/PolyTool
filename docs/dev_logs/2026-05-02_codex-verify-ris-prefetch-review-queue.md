# Codex Verification: RIS L3.1 Prefetch Review Queue

Date: 2026-05-02

## Verdict

PASS WITH FIXES

Implementation behavior verified. One docs-only inconsistency was fixed during verification:

- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` still said the filter supported three operating modes. It now says four.
- The same feature doc still listed `research-health` label counters as deferred. It now documents that `research-health` includes L3 prefetch filter counters.
- The near-term note now points operators to `hold-review` for label accumulation and keeps `dry-run` for unaffected ingestion.

No implementation code was changed during this verification.

## Files Changed By This Verification

- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` - docs-only correction for mode count, `research-health` counters, and near-term hold-review label accumulation guidance.
- `docs/dev_logs/2026-05-02_codex-verify-ris-prefetch-review-queue.md` - this verification log.

Existing L3.1 working-tree changes were inspected and left intact.

## Commands Run And Outputs

### Repo State

`git status --short`

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/relevance_filter/queue_store.py
 M tests/test_ris_relevance_filter.py
 M tests/test_ris_research_acquire_cli.py
 M tools/cli/research_acquire.py
?? docs/dev_logs/2026-05-02_codex-review-ris-prefetch-review-queue.md
?? docs/dev_logs/2026-05-02_ris-prefetch-review-queue-closeout.md
?? docs/dev_logs/2026-05-02_ris-prefetch-review-queue-fixes.md
```

After this verification log, one additional untracked file exists:

```text
?? docs/dev_logs/2026-05-02_codex-verify-ris-prefetch-review-queue.md
```

`git log --oneline -5`

```text
ac3aebc feat(ris): L3.1 prefetch review queue + label store + hold-review mode
a923e6a Academic Pipeline Improvements L0 - L2
1520e18 fix(ris): L3 pre-fetch filter v0 - Codex FAIL resolution (v1.1)
14a15a8 feat(ris): L3 cold-start lexical relevance filter with corpus simulation
7df7b9f feat(ris): scoped lexical refresh for L5 benchmark corpus
```

`git diff --stat`

```text
docs/CURRENT_DEVELOPMENT.md                        |   7 +-
docs/INDEX.md                                      |   6 +-
.../FEATURE-ris-prefetch-relevance-filter-v0.md    |  87 +++++++++---
docs/obsidian-vault/.obsidian/workspace.json       |   2 +-
.../.smart-env/event_logs/event_logs.ajson         |  14 +-
.../multi/Claude_Desktop_Current-Focus_md.ajson    |  18 +++
.../obsidian-vault/Claude Desktop/Current-Focus.md |   3 +-
packages/research/relevance_filter/queue_store.py  |  10 +-
tests/test_ris_relevance_filter.py                 |  17 +++
tests/test_ris_research_acquire_cli.py             | 151 +++++++++++++++++++++
tools/cli/research_acquire.py                      |  72 +++++++---
11 files changed, 339 insertions(+), 48 deletions(-)
```

`git diff --check`

```text
Exit code: 0
Only CRLF normalization warnings were printed for existing modified files; no whitespace errors were reported.
```

`git diff --cached --name-only`

```text
(no output)
```

### CLI Smoke

`python -m polytool --help`

Relevant output:

```text
research-acquire          Acquire a source from URL and ingest into knowledge store
research-health           Print RIS health status summary from stored run data
research-prefetch-review  List/label L3 hold-review queue items; export label counts for SVM
```

### Tests

`python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_eval_benchmark.py`

```text
collected 160 items
...
============================= 160 passed in 1.85s =============================
```

Test count: 160 passed, 0 failed.

### Requested CLI Help Checks

`python -m polytool research-acquire --help`

Relevant output:

```text
--prefetch-filter-mode {off,dry-run,enforce,hold-review}
                        Relevance pre-fetch filter mode (default: off). dry-
                        run: score and log but always ingest. enforce: skip
                        REJECT; ingest REVIEW with audit flag. hold-review:
                        ingest ALLOW only; skip REJECT; queue REVIEW without
                        ingesting.
```

`python -m polytool research-prefetch-review --help`

```text
usage: research-prefetch-review [-h] SUBCOMMAND ...

Manage the L3 prefetch relevance filter review queue and label store. Labeling
items here accumulates SVM training data for L3 v1.

positional arguments:
  SUBCOMMAND
    list      List all items in the prefetch review queue.
    label     Label a queue item allow or reject (appends to label store).
    counts    Show queue size and label store counts.

options:
  -h, --help  show this help message and exit
```

`python -m polytool research-prefetch-review list --help`

```text
usage: research-prefetch-review list [-h] [--queue-path PATH] [--json]

options:
  -h, --help         show this help message and exit
  --queue-path PATH  Override review queue JSONL path.
  --json             Output raw JSON instead of human-readable text.
```

`python -m polytool research-prefetch-review label --help`

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

`python -m polytool research-prefetch-review counts --help`

```text
usage: research-prefetch-review counts [-h] [--queue-path PATH]
                                       [--label-path PATH] [--json]

options:
  -h, --help         show this help message and exit
  --queue-path PATH  Override review queue JSONL path.
  --label-path PATH  Override label store JSONL path.
  --json             Output raw JSON instead of human-readable text.
```

`python -m polytool research-health --help`

```text
usage: research-health [-h] [--json] [--window-hours N] [--run-log PATH]
                       [--eval-artifacts PATH]

Print a RIS health status summary from stored run data.

options:
  -h, --help            show this help message and exit
  --json                Output raw JSON instead of human-readable table.
  --window-hours N      Look-back window in hours for run history (default:
                        48).
  --run-log PATH        Path to the run log JSONL file (default:
                        artifacts/research/run_log.jsonl).
  --eval-artifacts PATH
                        Path to eval artifacts JSONL (reserved for future
                        use).
```

Additional read-only counter check:

`python -m polytool research-health --json`

Relevant output:

```json
"prefetch_filter": {
  "pending_review_count": 0,
  "label_count": 0,
  "allowed_label_count": 0,
  "rejected_label_count": 0
}
```

## Mode Semantics Confirmation

Confirmed from tests and code inspection:

- Default mode remains `off`: `tools/cli/research_acquire.py` parser has `default="off"` and choices `["off", "dry-run", "enforce", "hold-review"]`.
- Dry-run logs but does not skip: `TestPrefetchFilterModes.test_dry_run_mode_logs_but_ingests` passed.
- Enforce skips REJECT only: `TestPrefetchFilterModes.test_enforce_skips_reject_only` passed, and enforce REVIEW is not queued.
- Hold-review ingests ALLOW, skips REJECT, queues REVIEW without ingestion: URL-mode tests passed for all three decisions.
- Search-mode hold-review is covered offline: `TestSearchModeHoldReview.test_search_mode_hold_review_queues_review_does_not_ingest` passed and asserts no ingest calls for REVIEW/REJECT papers.
- Queue write failure reports `queued_for_review=false` and `queue_error`: `TestPrefetchFilterModes.test_hold_review_queue_write_failure_reports_error` passed.
- Malformed JSONL is not silently dropped: `queue_store._read_jsonl` prints a `WARNING` to stderr, and `TestReviewQueueStore.test_malformed_jsonl_warns` passed.

## Artifact And Gitignore Check

`.gitignore` includes:

```text
/artifacts/
/artifacts/dossiers/
/artifacts/dossiers/**
/artifacts/**
```

`git status --short --ignored artifacts`

```text
!! artifacts/
```

`git ls-files artifacts`

```text
(no output)
```

No queue, label, or filter decision runtime artifacts are tracked or staged.

## Scope Creep Check

No implementation scope creep found:

- `git diff --name-only` shows changes confined to RIS docs, RIS relevance filter queue code, `research_acquire`, and targeted RIS tests, plus Obsidian metadata.
- `git diff -- pyproject.toml requirements.txt requirements-dev.txt setup.py` produced no output, so no new heavy dependencies were introduced.
- Existing dependency files already contain some ML-related dependencies for other repo areas, but this L3.1 diff does not add SVM, SPECTER2, scikit-learn/sklearn, torch, or sentence-transformers.
- No diffs touched trading/execution files, kill switch, risk manager, rate limiter, `py_clob_client`, Marker implementation, PaperQA2 implementation, n8n workflows, or multi-source harvesters.
- Docs now describe SVM/SPECTER2 as a future v1 path after label accumulation, not as implemented.
- Docs and CLI both keep `hold-review` opt-in; default remains `off`.

## Decisions Made

- Treated the stale feature-doc mode count and deferred `research-health` counter row as docs-only verification fixes.
- Did not run live `research-acquire` against the internet.
- Did not label queue items or mutate runtime label stores.
- Did not stage or commit any files.

## Open Questions Or Blockers

- None for L3.1 verification.
- Existing Obsidian workspace and `.smart-env` metadata changes remain in the working tree from prior activity; this verification did not modify or revert them.

## Remaining Manual Steps

- Operator can review and commit the L3.1 closeout changes plus this verification log.
- Label accumulation remains an operator action during future `hold-review` acquisition sessions.

## Codex Review Summary

Review tier: RIS verification, not a mandatory trading safety review.

Issues found:

- Docs-only stale text in the L3 feature doc.

Issues addressed:

- Corrected the mode count, `research-health` counter status, and near-term label accumulation guidance.
