---
tags: [work-packet, ris, ingestion, multi-source, stub]
date: 2026-04-27
status: stub
priority: low
phase: 2
target-layer: 4
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0)"
  - "[[Work-Packet - Pre-fetch SVM Topic Filter]] (Layer 3, to manage volume)"
---

# Work Packet (stub) — Multi-source Academic Harvesters

> [!INFO] Stub status
> Placeholder so cross-links resolve. Activate only after Layer 3 (pre-fetch filter) is operational. Without filtering, multi-source ingestion floods the eval gate.

## Layer

Layer 4 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

Five new fetcher implementations alongside `LiveAcademicFetcher` (which stays as the arXiv path):

1. **`SemanticScholarFetcher`** — primary metadata + PDF-URL aggregator across publishers and preprints. Handles rate limiting and authentication.
2. **`SSRNFetcher`** — finance/econ working papers. Session/cookie/redirect handling per the survey's "what we should not do" list.
3. **`NBERFetcher`** — macro/finance research. Working-group filtering.
4. **`OpenReviewFetcher`** — ML/CS conference papers when domain-relevant. Uses openreview-py.
5. **`CrossrefUnpaywallFetcher`** — DOI resolution and open-access PDF discovery, used to enrich and deduplicate across the other four.

Each fetcher returns a `raw_source` dict matching the existing `AcademicAdapter` schema. All five flow through Layer 3 pre-filter → Layer 1 parser → existing pipeline.

## Scope guards

- Do NOT modify `AcademicAdapter` — fetchers conform to its expected schema
- Each new fetcher is a separate class, not a polymorphic monolith
- No fetcher parallelizes downloads (respect each source's rate limits)
- Session/cookie handling is mandatory for SSRN and NBER — no naïve scraping
- Failure semantics match Layer 0: fall back gracefully, never silently store empty docs
- Deduplication by DOI / arxiv_id / source_id across all five fetchers

## Acceptance gates (to be detailed when activated)

1. Each fetcher successfully ingests 10+ papers from its source
2. Cross-source deduplication catches the same paper appearing on multiple sources (e.g., arXiv + SSRN preprint)
3. Rate-limit handling: no fetcher gets the operator banned from any source
4. Layer 3 pre-filter catches a meaningful fraction of off-topic papers (>30%) — confirms harvesters need the filter
5. End-to-end weekly throughput target: 50-200 on-topic papers ingested per week (post-filter)

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[11-Scientific-RAG-Pipeline-Survey]] — Semantic Scholar API, SSRN scrapers, NBER scraper, OpenReview entries have the full evaluations
- [[Work-Packet - Pre-fetch SVM Topic Filter]] — gating prerequisite for sane volume
