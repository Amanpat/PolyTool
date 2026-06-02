---
title: Ris L4 Multisource Academic Harvesters
type: reference
status: complete
completed: 2026-05-09
track: RIS
layer: 4
source_zone: repo
mirror_of: docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md
last_synced: '2026-05-25T22:14:18Z'
lifecycle: reviewed
generator: repo-sync
---

# FEATURE: RIS L4 Multi-source Academic Harvesters

**Completed:** 2026-05-09
**Track:** Research Intelligence System — Layer 4
**Dev log:** `docs/dev_logs/2026-05-09_ris-l4-multisource-academic-harvesters.md`

---

## Summary

Layer 4 of the four-layer scientific RAG target: metadata-only candidate discovery
from multiple academic sources.  Four harvesters are shipped.  Two sources (SSRN,
NBER) are explicitly documented as deferred with rationale.

**Pipeline position:** Harvesters produce `AcademicCandidate` records that feed into
the existing L3 relevance filter → review queue → L1 Marker parse → L2 query chain.
No PDF is downloaded by the harvester layer.  No Marker is called.  A candidate
does not become RAG-ready until it completes the L1 Marker queue path.

---

## What Shipped

### Core module: `packages/research/ingestion/academic_harvesters.py`

**`AcademicCandidate` dataclass** — normalized metadata record from any source:
- `source_url`, `title`, `abstract`, `authors`, `published_date`
- `source_name` — `"arxiv"` | `"semantic_scholar"` | `"crossref"` | `"openreview"`
- `canonical_ids` — `{arxiv_id, doi, s2_paper_id, openreview_id, ...}`
- `fields_of_study` — keyword tags when available
- `to_review_queue_record()` — produces a `ReviewQueueStore`-compatible dict

**`AcademicHarvesterBase` ABC** — defines `search(query, max_results)` and
`search_since(query, since_date, max_results)` (monitoring mode).

**Four harvester implementations:**

| Harvester | Source | API | Auth | PDF URL | Notes |
|-----------|--------|-----|------|---------|-------|
| `ArxivHarvester` | arXiv Atom API | Public | None | ✓ | Existing L0/L1 fetch path unchanged |
| `SemanticScholarHarvester` | S2 Graph API v1 | Public | Optional (`S2_API_KEY`) | ✓ (openAccessPdf) | Primary aggregator; returns externalIds |
| `CrossrefHarvester` | Crossref REST API | Public | None | ✗ | DOI resolution; abstract not always present |
| `OpenReviewHarvester` | OpenReview API v2 | Public | None | ✗ | ML conferences (NeurIPS/ICLR/ICML); backfill most useful |

**`dedup_candidates(candidates)`** — cross-source deduplication by any shared
canonical ID (`arxiv_id`, `doi`, `s2_paper_id`, `openreview_id`) with URL fallback.
First occurrence wins; later duplicates from other sources are dropped.

**`HARVESTER_REGISTRY`** — maps name → class for all 4 active sources.

**`SOURCE_CAPABILITY_MATRIX`** — structured capability flags + deferred-source rationale
for all 6 documented sources (4 active + SSRN deferred + NBER deferred).
Displayed by `research-harvest --list-sources`.

**`get_harvester(name, timeout, _http_fn)`** — factory with injectable HTTP function
for offline testing.

### CLI: `tools/cli/research_harvest.py`

```
python -m polytool research-harvest --search QUERY [options]
```

Options:
- `--source arxiv|semantic_scholar|crossref|openreview|all`  (default: `semantic_scholar`)
- `--max-results N`  (default: 20, per source)
- `--since YYYY-MM-DD`  monitoring mode: papers published on or after date
- `--force`  re-enqueue existing queue items
- `--dry-run`  print what would be enqueued without writing
- `--list-sources`  print the capability matrix

The CLI:
1. Calls the selected harvester(s) for metadata
2. Runs `dedup_candidates()` across all sources
3. Scores each with the existing `RelevanceScorer` (L3 lexical filter)
4. Enqueues allow/review decisions to `ReviewQueueStore`
5. Skips reject decisions (not enqueued)
6. Prints a summary with per-candidate action, source, and score

### Tests: `tests/test_academic_harvesters.py`

61 tests, all passing.  Coverage:
- All 4 harvesters: happy path, empty response, network error, malformed response
- `ArxivHarvester`: `search_since()` date filtering, multiple entries, `arxiv_id` extraction
- `SemanticScholarHarvester`: DOI fallback URL, S2-only URL, paper-with-no-id skipped
- `CrossrefHarvester`: JATS XML stripped from abstract, no-abstract paper, `from-pub-date` filter
- `OpenReviewHarvester`: API v2 `{"value": ...}` schema, API v1 plain-value fallback
- `dedup_candidates()`: by arxiv_id, by DOI, mixed DOI+arXiv aliases, cross-source,
  empty list, order preserved
- Registry: all 4 sources registered, factory types correct, unknown raises `KeyError`
- `SOURCE_CAPABILITY_MATRIX`: SSRN/NBER have `status=deferred`
- `AcademicCandidate.to_review_queue_record()`: key presence, deterministic ID
- Queue enqueue path: single enqueue, idempotent, force re-enqueue
- CLI smoke: `--list-sources`, `--dry-run` no write, successful enqueue, unknown source error,
  `--source all` hits 4 harvesters, cross-source dedup in CLI path

---

## Deferred Sources (documented, not blocked)

| Source | Reason for Deferral |
|--------|---------------------|
| **SSRN** | Session/cookie/redirect handling required. Community scrapers (`talsan/ssrn`, `karthiktadepalli1/ssrn-scraper`) exist but are flagged as brittle/maintenance-risk in the RAG pipeline survey. Requires Director approval before implementation. |
| **NBER** | HTML scraping required. The reference scraper (`ledwindra/nber`) was last updated 2021-2022 and may need modernization. No clean public API. Requires Director approval. |

Both are present in `SOURCE_CAPABILITY_MATRIX` with `status: "deferred"` and are
visible via `research-harvest --list-sources`.

---

## Integration Points

- **L3 (RelevanceScorer):** Harvested candidates are scored immediately in the CLI.
  Reject decisions are not enqueued.  Allow/review decisions enter the review queue.
- **Review queue (`ReviewQueueStore`):** Candidates append to
  `artifacts/research/prefetch_review_queue/review_queue.jsonl`.
  Managed via `research-prefetch-review list/label`.
- **L1 Marker queue:** After operator labeling, allowed candidates are enqueued to
  `research-marker-queue enqueue --url ARXIV_URL`. Current L1 direct enqueue supports
  arXiv IDs/URLs; DOI-only and OpenReview candidates remain review/discovery records
  until the operator resolves a parseable arXiv URL or a future DOI/PDF resolution path
  is added.
- **L2 query:** After Marker parse, papers become queryable via `research-query`.

The full pipeline flow is documented in the L1 Marker runbook
(`docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`) under "Top-Down Pipeline Flow."

---

## Definition of Done

- [x] Source abstraction/registry for academic candidate discovery
- [x] At least 3 real source adapters: arXiv, Semantic Scholar, Crossref, OpenReview (4 shipped)
- [x] Explicit source capability docs (metadata-only vs PDF-capable, backfill vs monitoring)
- [x] Normalized candidate records compatible with existing relevance/review queue flow
- [x] CLI/operator path: `research-harvest --search ... --source ...`
- [x] Dedupe/idempotency behavior across sources, including mixed DOI+arXiv aliases
- [x] No paper becomes RAG-ready without L1 Marker path (maintained invariant)
- [x] Adapter normalization tests with mocked responses
- [x] Registry/source selection tests
- [x] Dedupe/idempotency tests
- [x] Queue enqueue path tests
- [x] No network-required tests by default (all offline via `_http_fn`)
- [x] Deferred sources documented with rationale
- [x] Feature doc created
- [x] INDEX updated
- [x] CURRENT_DEVELOPMENT: Feature 3 closed, moved to Recently Completed
- [x] CURRENT_STATE updated
- [x] Dev log created

---

## Commands

```bash
# List all sources (active + deferred) with capability flags
python -m polytool research-harvest --list-sources

# Discover from Semantic Scholar (default)
python -m polytool research-harvest \
  --search "prediction markets microstructure" \
  --max-results 20

# Discover from all 4 active sources
python -m polytool research-harvest \
  --search "limit order book dynamics" \
  --source all \
  --max-results 10

# Monitoring mode: papers published since a date
python -m polytool research-harvest \
  --search "market making optimal strategy" \
  --source arxiv \
  --since 2024-01-01

# Dry run: see what would be enqueued
python -m polytool research-harvest \
  --search "prediction markets" \
  --source semantic_scholar \
  --dry-run

# After harvesting, label items
python -m polytool research-prefetch-review list

# After labeling, enqueue to Marker
python -m polytool research-marker-queue enqueue --url ARXIV_ID

# After Marker parse, query
python -m polytool research-query --question "market microstructure dynamics"
```
