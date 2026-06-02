---
title: L2 1 Chroma Linkage Command Contract Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_l2-1-chroma-linkage-command-contract-fix.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L2.1 Chroma Linkage Command Contract Fix

**Date:** 2026-05-23
**Status:** CLOSED

## Objective

Close the L2.1 Deliverable A handoff concern from Codex review: operator-facing
docs referenced a nonexistent `research-marker-queue embed-chroma` CLI subcommand.
The real operator path is `research-marker-queue index-done --reindex-chroma`,
with `research-marker-queue check-chroma-links --json` for verification.

## Files changed and why

- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - Replaced the nonexistent Chroma embedding command with
    `python -m polytool research-marker-queue index-done --reindex-chroma`.
  - Documented `--force` for intentional re-index/re-embed of items already
    recorded in `indexed.jsonl`.
  - Kept `python -m polytool research-marker-queue check-chroma-links --json`
    as the verification command.

No code, Chroma linkage behavior, semantic retrieval, query ranking, Marker parsing,
benchmark baselines, or 29-paper artifacts were changed.

## Commands run and output

### Session context

`git status --short`

Output: dirty worktree already present before this packet, including prior L2.1
changes in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`,
`packages/research/ingestion/marker_queue.py`,
`tools/cli/research_marker_queue.py`, `tests/test_ris_marker_queue.py`, plus many
Obsidian vault files. I treated those as pre-existing work and only edited the
requested runbook plus this dev log.

`git log --oneline -5`

Output:

```text
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
```

`python -m polytool --help`

Output: exit 0; CLI loaded and listed `research-marker-queue` and `research-query`.

### Command contract checks

`rg -n "embed-chroma" .`

Initial output:

```text
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md:738:python -m polytool research-marker-queue embed-chroma
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md:740:# Index AND embed in a single pass (skips a separate embed-chroma call)
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md:747:python -m polytool research-marker-queue embed-chroma --force
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md:776:so `--reindex-chroma` and `embed-chroma --force` are always safe to re-run. Chroma upsert
docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md:112:`python -m polytool research-marker-queue embed-chroma --help`
docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md:117:invalid choice: 'embed-chroma' (choose from enqueue, list, process,
docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md:166:`python -m polytool research-marker-queue embed-chroma`, but that CLI subcommand
docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md:177:documented `embed-chroma` subcommand to `embed_done_items_into_chroma()` or
docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md:69:python -m polytool research-marker-queue embed-chroma
```

Disposition:

- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` lines 738, 740, 747, 776:
  corrected in this packet.
- `docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md`: preserved as
  historical review record that identified the mismatch.
- `docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md`: preserved as historical
  implementation log; the correction is recorded here instead of rewriting history.

`rg -n "embed-chroma" docs/runbooks tests tools packages`

Output after runbook edit:

```text
<no matches>
```

`python -m polytool research-marker-queue index-done --help`

Output:

```text
usage: polytool research-marker-queue index-done [-h] [--ks-path PATH]
                                                 [--force]
                                                 [--no-extract-claims]
                                                 [--reindex-chroma]
                                                 [--chroma-path PATH] [--json]

options:
  -h, --help           show this help message and exit
  --ks-path PATH       Override KnowledgeStore SQLite path (default: project
                       default)
  --force              Re-index even items already recorded in indexed.jsonl
  --no-extract-claims  Skip automatic claim extraction after indexing.
                       Default: extract claims from each indexed paper via
                       body_file sidecar.
  --reindex-chroma     After indexing into KnowledgeStore, also embed each
                       paper body into the 'academic_papers' ChromaDB
                       collection using BAAI/bge-large-en-v1.5. Requires
                       chromadb + sentence-transformers. Idempotent: upserts
                       by deterministic chunk ID. Use 'check-chroma-links' to
                       verify linkage afterward.
  --chroma-path PATH   Override ChromaDB persist directory (default:
                       kb/rag/index)
  --json               Output summary as JSON
```

`python -m polytool research-marker-queue check-chroma-links --help`

Output:

```text
usage: polytool research-marker-queue check-chroma-links [-h] [--ks-path PATH]
                                                         [--chroma-path PATH]
                                                         [--collection NAME]
                                                         [--json]

options:
  -h, --help          show this help message and exit
  --ks-path PATH      Override KnowledgeStore SQLite path (default: project
                      default)
  --chroma-path PATH  Override ChromaDB persist directory (default:
                      kb/rag/index)
  --collection NAME   Override collection name (default: academic_papers)
  --json              Output report as JSON
```

### Focused tests

`python -m pytest tests/test_ris_marker_queue.py tests/test_research_query.py -q --tb=short`

Output:

```text
collected 288 items
287 passed, 1 skipped in 3.80s
```

## Decisions

- Preferred docs correction over adding a new CLI subcommand, per packet scope.
- Left historical dev logs untouched; this log records the correction and final
  operator-facing command contract.
- Did not update tests because the existing command-contract tests already assert
  `index-done --help` exposes `--reindex-chroma` and `check-chroma-links --help`
  exists.

## Result

Deliverable A is now cleanly closed from a handoff perspective: the operator-facing
runbook documents the real Chroma indexing/reindexing path and the verification
path, and no operator-facing runbook/test/tool/package references the nonexistent
command.

Deliverable B is safe to start. The remaining historical mentions are preserved
only in dev logs that document the prior implementation/review mismatch.

## Codex review summary

Review tier: skipped for this packet (docs-only command-contract correction; no
mandatory or recommended review files changed). Prior Codex review concern was
addressed by this runbook correction.
