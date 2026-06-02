---
title: Ris L4 Multisource Academic Harvesters
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_ris-l4-multisource-academic-harvesters.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log: RIS L4 Multi-source Academic Harvesters

**Date:** 2026-05-09
**Objective:** Complete RIS Layer 4 — multi-source academic candidate discovery
with at least 3 real source adapters, tests, CLI, and full completion protocol.
**Feature doc:** `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md`

---

## Source Matrix

| Source | API | Auth | Metadata | PDF URL | Mode | Status |
|--------|-----|------|----------|---------|------|--------|
| arXiv | Atom API | None | ✓ | ✓ (arxiv.org/pdf/) | Backfill + Monitoring | **Shipped** |
| Semantic Scholar | Graph API v1 | Optional (S2_API_KEY) | ✓ | ✓ (openAccessPdf) | Backfill + Monitoring | **Shipped** |
| Crossref | REST API | None | ✓ (abstract sometimes absent) | ✗ | Backfill + Monitoring | **Shipped** |
| OpenReview | API v2 | None | ✓ | ✗ | Backfill (conferences) | **Shipped** |
| SSRN | N/A | Session/cookie | — | — | — | **Deferred** |
| NBER | N/A (HTML) | None (but tricky) | — | — | — | **Deferred** |

---

## Files Changed

### New
- `packages/research/ingestion/academic_harvesters.py` — core harvester classes, registry, dedup, capability matrix
- `tools/cli/research_harvest.py` — `research-harvest` CLI command
- `tests/test_academic_harvesters.py` — 59 offline tests
- `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md` — feature doc (completion protocol)
- `docs/dev_logs/2026-05-09_ris-l4-multisource-academic-harvesters.md` — this file

### Modified
- `polytool/__main__.py` — registered `research-harvest` command + handler + help text
- `docs/CURRENT_DEVELOPMENT.md` — Feature 3 activated and moved to Recently Completed
- `docs/CURRENT_STATE.md` — L4 section updated from "stub" to "complete"
- `docs/INDEX.md` — L4 row added to features table
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` — top-down pipeline flow section added
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Multi-source Academic Harvesters.md` — status updated from stub

---

## Architecture

```
L4 Harvest          L3 Filter         Review Queue
research-harvest → RelevanceScorer → ReviewQueueStore
      ↓                                      ↓
AcademicCandidate                    research-prefetch-review
(metadata only)                      label/list

                            ↓ (after operator label: allow)

L1 Marker                  L2 Query
research-marker-queue  →   research-query
enqueue / warm-process     --question "..."
```

Key invariants preserved:
- No PDF is downloaded by the harvester layer
- No Marker is called by the harvester layer
- A candidate does not become RAG-ready until it completes the L1 Marker queue path
- `dedup_candidates()` removes cross-source duplicates by `arxiv_id > doi > s2_paper_id > openreview_id > url_hash`

---

## Commands / Tests Run

### Targeted L4 tests
```
python -m pytest tests/test_academic_harvesters.py -v --tb=short
Result: 59 passed, 0 failed, 2 warnings (deprecation fixed)
```

### Existing research tests (no regressions)
```
python -m pytest tests/test_academic_harvesters.py tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short
Result: 209 passed, 1 skipped
```

### CLI smoke (no network)
```
python -m polytool --help | grep research-harvest
Result: "research-harvest  L4: Multi-source academic discovery — arXiv/S2/Crossref/OpenReview (no PDF)"

python -m polytool research-harvest --help
Result: exit 0, help text with all flags

python -m polytool research-harvest --list-sources
Result: exit 0; printed all 4 active sources + SSRN [DEFERRED] + NBER [DEFERRED]
```

---

## DoD Pass/Fail

| Criterion | Status |
|-----------|--------|
| Source abstraction/registry | ✓ PASS |
| ≥3 tested adapters (3+ without SSRN/NBER) | ✓ PASS (4 shipped) |
| Explicit source capability docs | ✓ PASS (`SOURCE_CAPABILITY_MATRIX` + `--list-sources`) |
| Normalized candidates compatible with review queue | ✓ PASS |
| CLI operator path | ✓ PASS (`research-harvest`) |
| Dedupe/idempotency | ✓ PASS (tests cover arxiv_id, DOI, url, force) |
| No PDF / no Marker in harvester layer | ✓ PASS |
| No network in default tests | ✓ PASS (all offline via `_http_fn`) |
| Deferred sources documented | ✓ PASS (SSRN, NBER in matrix with rationale) |
| Feature doc | ✓ PASS |
| INDEX updated | ✓ PASS |
| CURRENT_DEVELOPMENT Feature 3 closed | ✓ PASS |
| CURRENT_STATE updated | ✓ PASS |
| Runbook updated with top-down flow | ✓ PASS |
| Dev log | ✓ PASS (this file) |

**Overall: L4 DoD PASS.**

---

## Completion Protocol Status

- [x] `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md` created
- [x] `docs/INDEX.md` updated (L4 row added)
- [x] `docs/CURRENT_DEVELOPMENT.md` Feature 3 moved to Recently Completed

---

## Deferred Source Caveats

**SSRN:** Requires session/cookie/redirect handling. Community scrapers
(`talsan/ssrn`, `karthiktadepalli1/ssrn-scraper`) exist but are flagged as
brittle in the RAG pipeline survey. Not implemented because the work packet
says "SSRN/NBER only if cleanly possible" and there is no clean public API.
Documented in `SOURCE_CAPABILITY_MATRIX` with `status: "deferred"`.
Visible via `research-harvest --list-sources`.

**NBER:** HTML scraping required. The `ledwindra/nber` reference scraper was last
updated 2021-2022. No clean public API. Documented similarly.

Both deferred sources require explicit Director approval before implementation.
L4 DoD does not require them — minimum 3 adapters is met with 4 active sources.

---

## Codex Review Summary

Tier: skip (CLI formatting, tests, discovery-only code — no execution/risk-manager/
kill-switch files changed). No mandatory Codex review files were touched.
