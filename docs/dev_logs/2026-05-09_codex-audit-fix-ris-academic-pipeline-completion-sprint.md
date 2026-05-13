# Codex Audit/Fix - RIS Academic Pipeline Completion Sprint

**Date:** 2026-05-09
**Objective:** Audit the RIS Academic Pipeline Completion Sprint and decide whether the
academic pipeline packets are complete enough to close. Small bounded fixes allowed.

## Completion Decision

**PASS WITH FIXES for L2 closure.**

L2 Academic Query is now complete enough to close for the bounded v1 scope:
`research-query` provides a functional operator CLI, query/retrieval/citation path,
Marker/RAG-ready filtering, graceful fallback, and tests for happy path plus bad docs.

**L4 is NOT complete.** It remains deferred and must not be relabeled as shipped. It
requires a separate Director workpacket because the scope is multiple fetchers,
source-specific rate/session handling, new dependencies, and network integration tests.

**Academic pipeline operator-ready verdict:** Operator-ready for L1 -> L2 local academic
query over Marker-ready KnowledgeStore documents. Not complete for L4 multi-source
harvesting, ChromaDB academic retrieval, page-level citations, or LLM synthesis.

## Review Findings

- Feature 3 activation was valid: active count was 2 before the sprint, L1 and L5
  prerequisites were complete, and L2 was the correct next packet.
- L2 implementation existed: `packages/research/synthesis/academic_query.py`,
  `tools/cli/research_query.py`, `polytool/__main__.py`, and
  `tests/test_research_query.py`.
- Blocking L2 issue found: `research-query` filtered to `source_family="academic"` but
  could still return legacy academic rows with `body_source="pdfplumber"`, missing
  metadata, or short Marker output if those rows already existed in the KnowledgeStore.
- L4 was not claimed complete by current feature docs after audit. It remains a stub.
- Completion protocol was mostly present: L2 feature doc existed, INDEX had an L2 row,
  and CURRENT_DEVELOPMENT listed L2 under Recently Completed. Several status docs still
  had stale "L2 stub" wording.
- No trading, PMXT, Track 1, execution, kill-switch, risk-manager, rate-limiter, or
  live-capital files were edited.

## Fixes Made

- Added a query-time Marker-ready guard in
  `packages/research/synthesis/academic_query.py`:
  `body_source == "marker"` and `body_length >= 5000`.
- Updated L2 tests in `tests/test_research_query.py`:
  - pdfplumber academic rows are not returned
  - missing metadata rows are not returned
  - short Marker rows are not returned
  - happy path remains covered
- Updated CLI help text:
  - `polytool --help` now says `research-query` queries Marker/RAG-ready academic corpus
  - `research-query --help` says Marker/RAG-ready papers only
  - `research-marker-queue --help` no longer says Linux/Docker reloads per paper in the
    top-level description
- Updated stale docs:
  - `docs/features/FEATURE-ris-l2-academic-query.md`
  - `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
  - `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
  - `docs/features/ris-marker-structural-parser-scaffold.md`
  - `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - `docs/CURRENT_DEVELOPMENT.md`
  - `docs/CURRENT_STATE.md`
  - `docs/INDEX.md`
  - `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - PaperQA2 RAG Control Flow.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Multi-source Academic Harvesters.md`
- Smart Env `.ajson` index files under `docs/obsidian-vault/.smart-env/` also changed
  as a side effect of editing the Obsidian notes; they were not used for code logic.

## Commands Run

Initial/session state:

```text
git status --short
Result: existing modified Smart Env files and untracked prior Codex L1 dev logs were present before this audit.

git log --oneline -5
Result:
26605fa feat(ris): L2 academic query - PaperQA2-inspired RAG control flow
c23e87e fix(ris): resolve Codex FAIL blockers - L1 rollout closeout
d2c0c27 feat(ris): L1 Marker Production Readiness Rollout - Feature 3 closed
932b839 pipeline improvements
4b57400 SVM scoring complete

python -m polytool --help
Result: exit 0; command list loaded.
```

Audit searches:

```text
git diff --stat
git diff --name-status
rg -n "PaperQA2|rag_ready|body_source=marker|pdfplumber|Multi-source|L4|Feature 3|Academic Pipeline" docs packages tools tests
Get-ChildItem docs/dev_logs -Filter '*ris-academic-pipeline-completion-sprint*.md'
Result: latest sprint log found at docs/dev_logs/2026-05-09_ris-academic-pipeline-completion-sprint.md.
```

Targeted and smoke tests:

```text
pytest -q tests/test_research_query.py
Result: 36 passed in 0.73s (final run after edge-case regression).

pytest -q tests/test_ris_marker_queue.py
Result: 114 passed, 1 skipped in 2.42s.

python -m polytool research-query --help
Result: exit 0; help says Marker/RAG-ready papers only.

python -m polytool research-marker-queue --help
Result: exit 0; help points Linux/Docker operators to warm-process for the validated IPC path.

python -m polytool research-query --question "market microstructure"
Result: exit 0; returned had_fallback=true with no citations because this machine has no academic docs in the KnowledgeStore.

python -m polytool --help
Result: exit 0; top-level help says research-query uses Marker/RAG-ready academic corpus.
```

Full smoke:

```text
python -m pytest tests/ -x -q --tb=short
Result: 1 failed, 2439 passed, 3 deselected, 21 warnings before stop.
Failure:
tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields
assert claim["actor"] == "heuristic_v1"
actual: "heuristic_v2_nofrontmatter"
```

This full-suite failure matches the unrelated pre-existing claim-extraction actor
mismatch already noted in the Claude L2 sprint log. It is outside this audit/fix scope.

## L2 Status

**PASS after fixes.**

- Functional path exists: `python -m polytool research-query --question "..."`
- Retrieval path exists: multi-angle `query_knowledge_store_for_rrf()` calls over
  `source_family="academic"`, grouped by source document.
- Answer/citation path exists: structured JSON citations with title, arxiv_id,
  source_url, snippet, body_source, and claim_count.
- Marker/RAG-ready guard exists at both ingest time and query time.
- pdfplumber is not a production fallback for L2 results.
- CLI/operator path is documented in the Marker queue runbook.
- Tests cover happy path and rejected/bad docs.

Known L2 v1 limits:

- No ChromaDB academic path yet because `body_source` is not indexed in chunk metadata.
- No page-level citations yet.
- No LLM synthesis yet.

## L4 Status

**FAIL / NOT COMPLETE.**

L4 was correctly left unshipped. The packet is still a stub and requires explicit
Director activation before implementation. Do not close L4 under this sprint.

## Completion Protocol Status

- L2 feature doc exists: `docs/features/FEATURE-ris-l2-academic-query.md`
- INDEX updated: `docs/INDEX.md`
- CURRENT_DEVELOPMENT correct: L2 in Recently Completed; Active count remains 2
  (Features 1 and 2); L4 deferred.
- CURRENT_STATE updated with an L2 completion section and L4 deferral.
- Obsidian Current-Focus and work packets updated so live status docs no longer call
  L2 a stub.

## Remaining Work

- L4 Multi-source Academic Harvesters: open a Director workpacket before implementing.
- L2.1 ChromaDB academic query path: store `body_source` in chunk metadata before using
  Chroma for academic retrieval.
- Page-level citations: require Marker page metadata to be indexed/queryable.
- LLM synthesis: future `research-query` provider integration.
- Existing full-suite blocker: claim extraction actor expectation mismatch
  (`heuristic_v2_nofrontmatter` vs `heuristic_v1`).

## Codex Review Summary

Tier: recommended-style audit of RIS query/docs/tests. One L2 blocker found and fixed:
legacy/bad academic rows could be cited by `research-query`. No mandatory trading or
live-capital files reviewed or changed.
