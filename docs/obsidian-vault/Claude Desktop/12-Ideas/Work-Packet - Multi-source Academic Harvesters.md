---
tags: [work-packet, ris, ingestion, multi-source, stub]
date: 2026-04-29
status: stub
priority: low
phase: 2
target-layer: 4
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped)"
  - "[[Work-Packet - Marker Structural Parser Integration]] (Layer 1 — production rollout)"
  - "[[Work-Packet - Pre-fetch SVM Topic Filter]] (Layer 3 — to manage volume from new sources)"
---

# Work Packet (stub) — Multi-source Academic Harvesters

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate after Layer 3 (pre-fetch filter) is operational. Without filtering, multi-source ingestion floods the eval gate. Layer 1 must also be operational so all parsed content uses Marker consistently — adding new sources before Marker is the production parser would compound the inconsistent-corpus problem.

## Layer

Layer 4 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

Five new fetcher implementations alongside `LiveAcademicFetcher` (which stays as the arXiv path). **Each fetcher supports two modes — backfill and monitoring — sharing infrastructure but triggered differently:**

- **Backfill mode** — operator specifies a topic and date range; fetcher queries the source for all matching papers in that range. Used once when a topic is added to the active research set, then on demand. Returns hundreds of candidates per topic.
- **Monitoring mode** — fetcher checks the source on a schedule for new arrivals matching active topics. Returns small batches (0-20 papers per check). Runs continuously.

Both modes return candidates as metadata only (title, abstract, source URL). Each candidate flows through Layer 3 (pre-filter) → Layer 1 (Marker parser) → existing pipeline. PDF download only happens after the pre-filter says on-topic.

The five fetchers:

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
- Deduplication by DOI / arxiv_id / source_id across all five fetchers — same paper appearing on arXiv and SSRN ingests once
- Backfill mode is operator-triggered (CLI command), not scheduled. Monitoring mode is scheduled.
- Pre-filter decision is made on metadata before any PDF download — do not waste bandwidth on off-topic papers

## Reference materials for architect

The architect should read these before refining this stub:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — five harvester entries are directly relevant:
   - **Semantic Scholar API + S2FOS + SPECTER2** — primary aggregator, full evaluation in survey
   - **SSRN scrapers** (talsan/ssrn, karthiktadepalli1/ssrn-scraper) — patterns for session/cookie handling, JEL-code search. Brittle; survey explicitly flags maintenance risk.
   - **NBER scraper** (ledwindra/nber) — patterns for working-group filtering. Last commit 2021-2022, may need modernization.
   - **OpenReview Scraper** (pranftw/openreview_scraper) — keyword filtering pattern, but no PDF download logic
   - **OpenReview Finder** (danmackinlay/openreview_finder) — better reference, includes SPECTER2 + ChromaDB integration
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 4 in "Adopt" specifies this combination, with the explicit warning to handle SSRN/NBER session issues per the "what we should not do" list.
3. **PolyMaster Roadmap section "Multi-Layer Data Stack"** in the master roadmap — establishes the date-range and source-tier metadata patterns. Backfill mode reuses this thinking.

## Acceptance gates (to be detailed when activated)

1. Each of five fetchers successfully ingests 10+ papers from its source in monitoring mode
2. Each of five fetchers successfully completes a backfill run with operator-specified topic and date range, returning ≥20 candidates
3. Cross-source deduplication catches the same paper appearing on multiple sources (e.g., arXiv preprint + SSRN posted version) — verified on a known overlap set
4. Rate-limit handling: no fetcher gets the operator banned from any source (test with deliberately aggressive request rates and verify back-off)
5. Layer 3 pre-filter catches a meaningful fraction of off-topic papers (>30%) — confirms harvesters need the filter
6. End-to-end weekly throughput target: 50-200 on-topic papers ingested per week (post-filter)
7. Backfill of foundational papers: operator runs backfill for "market microstructure 2000-2020" and the system retrieves at least 50 known-relevant papers (verified against a hand-curated golden set)

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision (item 4)
- [[Work-Packet - Marker Structural Parser Integration]] — parser these fetchers feed into
- [[Work-Packet - Pre-fetch SVM Topic Filter]] — gating prerequisite for sane volume
- [[11-Scientific-RAG-Pipeline-Survey]] — Semantic Scholar, SSRN, NBER, OpenReview entries
