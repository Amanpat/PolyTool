---
title: "Work Packet — Multi-source Academic Harvesters"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
tags: [work-packet, ris, ingestion, multi-source, complete]
target_agent: claude-code
acceptance_criteria:
  - See body for full criteria
---

# Work Packet — Multi-source Academic Harvesters

> [!SUCCESS] Complete (2026-05-09) — arXiv path operator-tested
> L4 shipped: 4 harvesters (arXiv, Semantic Scholar, Crossref, OpenReview),
> `AcademicCandidate` dataclass, `dedup_candidates()`, `research-harvest` CLI,
> `SOURCE_CAPABILITY_MATRIX`. SSRN and NBER explicitly deferred (session/cookie
> brittleness / outdated scrapers). 61 tests pass after Codex dedupe-audit fix.
> Feature doc and runbook updated.
> See `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md`.
>
> **Operator-tested v1 (2026-05-09):** arXiv path validated through the full pipeline
> (enqueue→warm-process→index-done→research-query) with 3 papers. Crossref/OpenReview
> candidates may need operator resolution to an arXiv URL before L1 Marker queue
> can parse them. SSRN/NBER remain deferred.

> [!INFO] Former stub status (resolved)
> This packet was a placeholder so cross-links could resolve. L1 and L3 prerequisites were met, but
> the packet remained unactivated and incomplete. It required a separate Director
> workpacket because the original full scope included multiple new sources,
> source-specific rate/session handling, new dependencies, and network integration tests.

## Layer

Layer 4 of the [[Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What shipped

**Codex audit note (2026-05-09):** accepted L4 scope is the four-adapter,
metadata-only implementation in `packages/research/ingestion/academic_harvesters.py`:
`ArxivHarvester`, `SemanticScholarHarvester`, `CrossrefHarvester`, and
`OpenReviewHarvester`. SSRN and NBER are deferred with explicit rationale, and
Crossref is a primary metadata source rather than a separate Crossref/Unpaywall
PDF resolver. The original planning notes below are superseded where they still
say "five fetchers" or imply SSRN/NBER were shipped.

Five new fetcher implementations alongside `LiveAcademicFetcher` (which stays as the arXiv path). **Each fetcher supports two modes — backfill and monitoring — sharing infrastructure but triggered differently:**

- **Backfill mode** — operator specifies a topic and date range; fetcher queries the source for all matching papers in that range. Used once when a topic is added to the active research set, then on demand. Returns hundreds of candidates per topic.
- **Monitoring mode** — fetcher checks the source on a schedule for new arrivals matching active topics. Returns small batches (0-20 papers per check). Runs continuously.

Both modes return candidates as metadata only (title, abstract, source URL). Each candidate flows through Layer 3 (pre-filter) → Layer 1 (Marker parser) → existing pipeline. PDF download only happens after the pre-filter says on-topic.

Superseded original five-fetcher target:

1. **`SemanticScholarFetcher`** — primary metadata + PDF-URL aggregator across publishers and preprints. Handles rate limiting and authentication. Both backfill (search by topic across all of history) and monitoring (papers added since last check) modes.
2. **`SSRNFetcher`** — finance/econ working papers. Session/cookie/redirect handling per the survey's "what we should not do" list. Both modes.
3. **`NBERFetcher`** — macro/finance research. Working-group filtering. Both modes.
4. **`OpenReviewFetcher`** — ML/CS conference papers when domain-relevant. Uses openreview-py. Backfill is most useful here (papers from past NeurIPS/ICLR/ICML).
5. **`CrossrefUnpaywallFetcher`** — DOI resolution and open-access PDF discovery. Used to enrich metadata and find PDFs for papers initially discovered via the other four. Not a primary harvester.

The existing `LiveAcademicFetcher` (arXiv) gets a backfill mode added in this packet too — currently it only supports per-URL fetch and search. Backfill across date ranges and topics rounds out the arXiv path.

## Scope guards

- Do NOT modify `AcademicAdapter` — fetchers conform to its expected schema (sets `body_text` from Marker output)
- Each new fetcher is a separate class, not a polymorphic monolith
- No fetcher parallelizes downloads (respect each source's rate limits)
- Session/cookie handling is mandatory for SSRN and NBER — no naïve scraping
- Failure semantics match Layer 0/1: fall back gracefully, never silently store empty docs
- Deduplication by DOI / arxiv_id / source_id across active sources; same-paper aliases are caught before review enqueue
- Backfill mode is operator-triggered (CLI command), not scheduled. Monitoring mode is scheduled.
- Pre-filter decision is made on metadata before any PDF download — do not waste bandwidth on off-topic papers

## Reference materials for architect

The architect should read these before refining this stub:

1. **`[[legacy/Claude Desktop/08-Research/11-Scientific-RAG-Pipeline-Survey]]`** — five harvester entries are directly relevant:
   - **Semantic Scholar API + S2FOS + SPECTER2** — primary aggregator, full evaluation in survey
   - **SSRN scrapers** (talsan/ssrn, karthiktadepalli1/ssrn-scraper) — patterns for session/cookie handling, JEL-code search. Brittle; survey explicitly flags maintenance risk.
   - **NBER scraper** (ledwindra/nber) — patterns for working-group filtering. Last commit 2021-2022, may need modernization.
   - **OpenReview Scraper** (pranftw/openreview_scraper) — keyword filtering pattern, but no PDF download logic
   - **OpenReview Finder** (danmackinlay/openreview_finder) — better reference, includes SPECTER2 + ChromaDB integration
2. **`[[legacy/Claude Desktop/09-Decisions/Decision - Scientific RAG Architecture Adoption]]`** — item 4 in "Adopt" specifies this combination, with the explicit warning to handle SSRN/NBER session issues per the "what we should not do" list.
3. **PolyMaster Roadmap section "Multi-Layer Data Stack"** in the master roadmap — establishes the date-range and source-tier metadata patterns. Backfill mode reuses this thinking.

## Acceptance gates (to be detailed when activated)

**Codex audit status (2026-05-09):** L4 is accepted under the implemented MVP
gate: at least 3 real tested adapters (4 shipped), normalized candidates, source
registry/selection, CLI/operator path, review-queue compatibility, cross-source
dedupe including mixed DOI+arXiv aliases, offline tests, and no L1 Marker bypass.
The older five-fetcher/live-network acceptance ideas below remain future
operator validation goals, not requirements for the completed MVP.

1. Future full-scope validation: each deferred/full source successfully ingests 10+ papers from its source in monitoring mode
2. Future full-scope validation: each deferred/full source successfully completes a backfill run with operator-specified topic and date range, returning >=20 candidates
3. Cross-source deduplication catches the same paper appearing on multiple sources (e.g., arXiv preprint + SSRN posted version) — verified on a known overlap set
4. Rate-limit handling: no fetcher gets the operator banned from any source (test with deliberately aggressive request rates and verify back-off)
5. Layer 3 pre-filter catches a meaningful fraction of off-topic papers (>30%) — confirms harvesters need the filter
6. End-to-end weekly throughput target: 50-200 on-topic papers ingested per week (post-filter)
7. Backfill of foundational papers: operator runs backfill for "market microstructure 2000-2020" and the system retrieves at least 50 known-relevant papers (verified against a hand-curated golden set)

## Cross-references

- [[legacy/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture]] — parent design
- [[Claude Desktop/09-Decisions/Decision - Scientific RAG Architecture Adoption]] — adoption decision (item 4)
- [[claude-memory/work-packets/work-packet-marker-structural-parser-integration]] — parser these fetchers feed into
- [[claude-memory/work-packets/work-packet-pre-fetch-svm-topic-filter]] — gating prerequisite for sane volume
- [[Claude Desktop/08-Research/11-Scientific-RAG-Pipeline-Survey]] — Semantic Scholar, SSRN, NBER, OpenReview entries
