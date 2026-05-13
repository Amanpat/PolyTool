# Dev Log: Codex Audit/Fix - RIS L4 Multi-source Academic Harvesters

**Date:** 2026-05-09
**Objective:** Audit, fix, and final-gate RIS L4 Multi-source Academic Harvesters.
**Final decision:** PASS - L4 is complete for the implemented metadata-only MVP and the
academic pipeline is ready for operator testing with the caveats below.

---

## Findings

- L4 is not docs-only: `packages/research/ingestion/academic_harvesters.py` contains
  four real metadata adapters (`ArxivHarvester`, `SemanticScholarHarvester`,
  `CrossrefHarvester`, `OpenReviewHarvester`), a source registry, source factory,
  normalized `AcademicCandidate`, source capability matrix, and dedupe helper.
- `tools/cli/research_harvest.py` provides an operator path:
  `research-harvest --search ... --source all|arxiv|semantic_scholar|crossref|openreview`.
- The CLI keeps L4 metadata-only: no PDF download, no Marker call, no indexing. It scores
  with the L3 relevance filter and enqueues allow/review candidates to `ReviewQueueStore`.
- L1/RAG safety is preserved. L4 does not mark anything `rag_ready`; L2 still filters to
  `body_source=marker` and `body_length >= 5000`.
- SSRN and NBER are truthfully deferred in `SOURCE_CAPABILITY_MATRIX` and operator docs.
- Blocker found: cross-source dedupe only used the highest-priority key per candidate.
  A Crossref DOI-only record followed by a Semantic Scholar record with both DOI and arXiv
  ID could duplicate the same paper.
- Blocker found: `research-harvest --json` appeared in help but was not implemented.
- Stale docs found: several current docs still said L4 was stub/deferred after the L4
  completion commit.

---

## Fixes Made

- Fixed `dedup_candidates()` to match on any shared canonical ID (`arxiv_id`, `doi`,
  `s2_paper_id`, `openreview_id`) with URL fallback.
- Added DOI normalization and transitive alias learning, so a skipped DOI+arXiv duplicate
  also teaches the arXiv alias for later candidates.
- Added two tests for mixed DOI+arXiv duplicate shapes.
- Removed the unused `research-harvest --json` CLI flag and corrected `--force` help text.
- Synced stale L4 status docs across:
  - `docs/CURRENT_DEVELOPMENT.md`
  - `docs/CURRENT_STATE.md`
  - `docs/INDEX.md`
  - `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
  - `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
  - `docs/features/FEATURE-ris-l2-academic-query.md`
  - `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md`
  - `docs/features/ris-marker-structural-parser-scaffold.md`
  - `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Multi-source Academic Harvesters.md`

---

## Adapter / Source Matrix

| Source | Adapter | Status | Auth | Monitoring | Review queue compatible | L1 parse caveat |
|--------|---------|--------|------|------------|-------------------------|-----------------|
| arXiv | `ArxivHarvester` | Shipped | None | Yes | Yes | Direct arXiv ID/URL enqueue works |
| Semantic Scholar | `SemanticScholarHarvester` | Shipped | Optional `S2_API_KEY` | Yes | Yes | End-to-end direct only when an arXiv ID/URL is present; DOI/S2-only needs operator resolution |
| Crossref | `CrossrefHarvester` | Shipped | None | Yes | Yes | DOI-only candidates need operator resolution to arXiv/current parseable source |
| OpenReview | `OpenReviewHarvester` | Shipped | None | Backfill-oriented | Yes | OpenReview candidates need operator resolution to arXiv/current parseable source |
| SSRN | None | Deferred | Session/cookie | Deferred | No | Requires Director approval |
| NBER | None | Deferred | HTML scrape | Deferred | No | Requires Director approval |

---

## Completion Protocol Status

- Feature doc exists: `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md`
- Index updated: `docs/INDEX.md`
- CURRENT_DEVELOPMENT moved L4 to Recently Completed.
- Codex audit/fix dev log created: this file.

Feature 3 activation/closeout status is correct after docs sync: L4 is complete and is
not occupying an Active feature slot. Active count remains 2 (Track 2 Paper Soak and RIS
Operational Readiness Phase 2A).

---

## Commands Run

Session-start checks:

```text
git status --short
Result: dirty worktree with RIS docs/query/CLI files already modified; no trading path listed.

git log --oneline -5
Result:
dbcf2ec feat(ris): L4 Multi-source Academic Harvesters - Feature 3 closed
26605fa feat(ris): L2 academic query - PaperQA2-inspired RAG control flow
c23e87e fix(ris): resolve Codex FAIL blockers - L1 rollout closeout
d2c0c27 feat(ris): L1 Marker Production Readiness Rollout - Feature 3 closed
932b839 pipeline improvements

python -m polytool --help
Result: exit 0; research-harvest listed under RIS commands.
```

Required audit commands:

```text
git diff --stat
Result: dirty RIS/docs/query tree; no trading/PMXT path in changed file list.

git diff --name-status
Result: docs/RIS files, packages/research/*, tools/cli/research_* and tests; no trading/PMXT path.

git diff --name-status -- execution polytool/simtrader packages/polymarket packages/simtrader tools/cli/simtrader.py risk_manager.py rate_limiter.py kill_switch.py
Result: no output.

rg -n "Semantic Scholar|SemanticScholar|Crossref|Unpaywall|OpenReview|SSRN|NBER|Multi-source|source registry|academic harvester|research.*discover|body_source=marker|rag_ready" docs packages tools tests
Result: L4 code/tests/docs found; no trading code implicated.
```

Targeted and regression tests:

```text
python -m pytest -q tests/test_academic_harvesters.py
Result: 61 passed in 0.93s

python -m pytest -q tests/test_research_query.py tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py
Result: 194 passed, 1 skipped in 3.50s
```

CLI help/smoke, no live network:

```text
python -m polytool research-harvest --help
Result: exit 0; options include --search, --source, --max-results, --since, --force, --dry-run, --list-sources, --queue-path.

python -m polytool research-harvest --list-sources
Result: exit 0; prints arxiv, semantic_scholar, crossref, openreview, ssrn [DEFERRED], nber [DEFERRED].

python -m polytool research-query --help
Result: exit 0.

python -m polytool research-marker-queue --help
Result: exit 0.

python -m polytool research-prefetch-review --help
Result: exit 0.
```

Project smoke:

```text
python -m pytest tests/ -x -q --tb=short
Result: FAILED after 2500 passed, 3 deselected, 21 warnings.
Failure:
tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields
AssertionError: expected actor == "heuristic_v1"; actual was "heuristic_v2_nofrontmatter".
Assessment: unrelated existing RIS claim-extraction regression; L4 files were already passed earlier in this full run.
```

---

## Final Decision

**L4 accepted:** PASS.

Minimum acceptance status:

| Criterion | Result |
|-----------|--------|
| At least 3 tested adapters | PASS - 4 shipped and tested |
| Normalized candidate records | PASS - `AcademicCandidate` |
| Source registry/selection | PASS - `HARVESTER_REGISTRY`, `get_harvester()`, `--source` |
| CLI/operator path | PASS - `research-harvest` |
| Enqueue/review flow compatibility | PASS - `ReviewQueueStore` path; current L1 parse caveat documented |
| Dedupe/idempotency | PASS - fixed mixed canonical-ID aliases; queue idempotency tested |
| No default live network/auth tests | PASS - tests inject `_http_fn` |
| No L1 Marker-ready bypass | PASS - L4 metadata only; L2 Marker guard intact |
| No trading/PMXT/Track 1/live-capital files touched | PASS - diff pathspec returned no output |

**Academic pipeline ready for operator testing:** PASS, with caveat that end-to-end
harvest-to-Marker testing should start with arXiv or Semantic Scholar candidates that
carry an arXiv ID. Crossref/OpenReview are valid discovery/review sources but need
operator resolution to a parseable arXiv URL before the current Marker queue can parse.

---

## Remaining Risks / Operator Test Plan

Risks:

- Live source APIs were not called in this audit by instruction. Operator should expect
  real-world rate-limit and response-shape drift to surface during first live runs.
- Crossref/OpenReview candidates do not currently have a direct non-arXiv Marker queue
  path. This is documented as an operator caveat, not hidden.
- Full repo smoke remains blocked by an unrelated claim-extraction actor mismatch.

Operator test plan:

1. Run `python -m polytool research-harvest --list-sources`.
2. Dry-run arXiv: `python -m polytool research-harvest --search "prediction markets microstructure" --source arxiv --max-results 5 --dry-run`.
3. Dry-run all sources with small limits: `python -m polytool research-harvest --search "market microstructure" --source all --max-results 2 --dry-run`.
4. Run one real enqueue to the review queue using arXiv or S2 with arXiv ID.
5. Label one candidate with `research-prefetch-review label`.
6. Enqueue to Marker with `research-marker-queue enqueue --url ARXIV_ID`.
7. Process inside Docker/GPU with `research-marker-queue warm-process`.
8. Query with `research-query --question "..."` and verify only `body_source=marker` papers appear.

