# Codex Review - L3.2 Prefetch Label Discovery Mode

Date: 2026-05-05
Reviewer: Codex
Verdict: PASS

## Objective

Review L3.2 Prefetch Label Discovery Mode after Claude Prompt A and B. Confirm
the feature queues label candidates from metadata only and does not ingest,
parse, index, or train models.

## Files Inspected

- `git diff`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `packages/research/relevance_filter/*`
- `tools/cli/research_prefetch_discover.py`
- `tools/cli/research_prefetch_review.py`
- `polytool/__main__.py`
- `tests/test_ris_relevance_filter.py`
- `tests/test_ris_prefetch_discovery.py`
- `docs/dev_logs/*prefetch*discovery*`

## Findings

Blocking findings: none.

Non-blocking documentation hygiene: `docs/CURRENT_DEVELOPMENT.md` and
`docs/obsidian-vault/Claude Desktop/Current-Focus.md` still use
pre-implementation wording such as "implementation not yet started" /
"Next action: implement" in the active L3.2 entry. This does not affect the
review verdict because the implementation log exists and the requested
metadata-only/code-scope checks pass, but close-out docs should update that
status.

## Check Results

1. Feature 3 is L3.2: PASS. `docs/CURRENT_DEVELOPMENT.md` has Feature 3 as
   "RIS L3.2 Prefetch Label Discovery Mode".
2. Option A Marker IPC warm-worker deferred/revisit reminder: PASS. The work
   packet, Current Development, and Current Focus all state Docker/Linux IPC
   warm-worker Option A is deferred, not canceled, and must be revisited after
   the L3/SVM stream or before L2 production.
3. Discovery command uses metadata only: PASS. `arxiv_search_metadata_only()`
   calls the arXiv Atom query endpoint and parses title, abstract, canonical
   URL, authors, and published date.
4. No PDF download, Marker parse, ingest_external, chunking, embedding, or
   indexing occurs: PASS. The new discover command does not import or call the
   PDF, Marker, ingest, chunk, embedding, or indexing paths. Tests assert no
   PDF URL is called and exactly one Atom API URL is used.
5. Existing review queue/label store reused: PASS. The discover command uses
   `ReviewQueueStore`, `LabelStore`, and `candidate_id_from_url` from
   `packages.research.relevance_filter.queue_store`.
6. ALLOW candidates can be queued for positive labels: PASS.
   `--include-allow` adds ALLOW to the queued decision set, and
   `--decision-filter allow,review` / `all` also support ALLOW queueing.
7. Duplicate handling is idempotent: PASS by default. `ReviewQueueStore.enqueue`
   skips existing `candidate_id` values unless the operator explicitly passes
   `--force`.
8. Audit fields include score, decision, reason codes, matched terms, config
   version: PASS. Enqueued records include `score`, `raw_score`, `decision`,
   `reason_codes`, `matched_terms`, thresholds, and `config_version`.
9. No SVM/SPECTER2, L2, L4, n8n, or trading scope creep: PASS. SVM is only
   referenced as a future trigger/progress target. No training or model code is
   added. L2/L4/n8n/trading are documented as non-goals and not touched in the
   new command path.
10. Tests are offline/deterministic and pass: PASS. The discovery tests inject
    `_http_fn` fixtures and do not perform live arXiv or PDF requests.

## Commands Run

```powershell
git status --short
```

Exit: 0. Output showed a dirty worktree from Claude/Obsidian changes, including
the new `tools/cli/research_prefetch_discover.py`,
`tests/test_ris_prefetch_discovery.py`, and L3.2 dev logs. No files were
reverted.

```powershell
git log --oneline -5
```

Exit: 0.

```text
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
38a13c2 docs(ris): short-paper Marker smoke validation - systematic timeout diagnosis
```

```powershell
python -m polytool --help
```

Exit: 0. CLI loaded successfully and listed
`research-prefetch-discover  L3.2 metadata-only arXiv discovery: score + enqueue for labels (no PDF)`.

```powershell
git diff
```

Exit: 0. Inspected tracked diffs for docs, `queue_store.py`, and
`polytool/__main__.py`. Untracked discover/test files were inspected directly
with `Get-Content`.

```powershell
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_discovery.py
```

Exit: 0.

```text
collected 99 items
============================= 99 passed in 1.12s ==============================
```

```powershell
python -m polytool research-prefetch-discover --help
```

Exit: 0.

```text
usage: research-prefetch-discover [-h] --search QUERY [--source-family FAMILY]
                                  [--max-results N] [--include-allow]
                                  [--decision-filter DECISIONS] [--force]
                                  [--queue-path PATH] [--label-path PATH]
                                  [--filter-config PATH] [--timeout SECONDS]
                                  [--json] [--dry-run]

L3.2 Prefetch Label Discovery: search arXiv metadata only, score candidates
with the lexical relevance filter, and enqueue to the prefetch review queue.
No PDFs are downloaded. No ingestion, no embeddings, no Marker.
```

```powershell
python -m polytool research-prefetch-review counts
```

Exit: 0.

```text
Prefetch review queue : 27 total queued  |  0 pending unlabeled
Labels (in queue)     : 27 labeled  |  7 allow  |  20 reject
SVM trigger (>=30 each) : need 23 more allow, 10 more reject
```

```powershell
git diff --check
```

Exit: 0. Output contained only line-ending warnings for existing modified
files; no whitespace errors were reported.

## Decisions

- Did not run live arXiv, per instruction.
- Did not implement code fixes. No code fixes were needed for the requested
  scope.
- Treated SVM references in CLI output as progress/status only, not training
  implementation.

## Live Metadata Discovery Use

Yes. Live metadata discovery can be used for label accumulation. The operator
can run `research-prefetch-discover` to fetch arXiv metadata, score title and
abstract with the existing lexical filter, and queue candidates into the
existing review queue for `research-prefetch-review label`. The current queue
state is 7 allow / 20 reject labels in queue scope, so the remaining target is
23 allow and 10 reject labels to reach the >=30 allow + >=30 reject SVM trigger.

## Open Questions / Blockers

- No blocker for metadata-only label accumulation.
- Close-out docs should update pre-implementation wording once the operator is
  ready to mark L3.2 shipped.

## Codex Review Summary

Tier: recommended/light review. No execution, live-trading, kill-switch, rate
limit, order-placement, or capital-risk code was touched.

Result: PASS. The feature queues label candidates from metadata only and does
not ingest, parse PDFs, index, embed, chunk, or train models.
