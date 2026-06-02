---
title: "Idea — RIS Retrieval Quality Polish Backlog"
type: idea
status: active
source_zone: claude_memory
created: 2026-05-29
last_updated: 2026-05-29
lifecycle: draft
tags: [idea, ris, retrieval, polish, post-v1, todo]
priority: low
blocking: none
---

# Idea — RIS Retrieval Quality Polish Backlog

> [!NOTE] Status: TODO — optional polish, not blocking
> These items were surfaced by a manual operator verification of `research-query`
> against the Marker corpus on 2026-05-29 (Opus 4.8 session). The pipeline PASSED
> end-to-end verification — correct papers, correct chunks, accurate source-grounded
> numbers, semantic retrieval path engaged, `had_fallback=false`. These are
> retrieval-ranking refinements, NOT correctness fixes. Demo-ready v1 stands as-is.

## What triggered this

Two verification queries against `acad-a1921b9a` ("The Anatomy of a Decentralized
Prediction Market", arxiv:2604.24366):

- Query 1 ("trade-direction sign-agreement rate") — clean pass. Right paper ranked #1,
  `body_source=marker`, `had_fallback=false`, `retrieval_mode=semantic`, snippet contained
  the correct ~59% / 67% / 60% figures matching the source.
- Query 2 (step-back variant) — correct answer retrieved (#2) with the right numbers, BUT
  a reference-list chunk from a different paper ("ForesightFlow", 2605.00493) ranked #1
  with `paper_score=0.60` despite containing zero findings — just a bibliography that
  keyword-matched on "trade direction from intraday data" (a Lee-Ready citation).

## The items

### Item 1 — Filter reference-list / bibliography chunks (PRIMARY)

**Necessity:** Optional for demo-ready v1. **Likely necessary before production-ready**
and definitely before a non-coder relies on answers. Severity scales with corpus size —
minor at 21 papers, compounding at 200+ papers because bibliographies become a larger
fraction of total chunks.

**Problem:** Reference lists and bibliographies are being embedded and retrieved as if
they were content. They keyword-match queries densely (author names, paper titles, "trade
direction", "et al.") but contain no findings. In query 2 a bibliography chunk outranked
the chunk that actually answered the question.

**Proposed fix:** At index time, detect Marker section headers matching
`References` / `Bibliography` and either (a) drop those chunks from the embedding set, or
(b) tag them `section=references` and exclude by default at query time. Marker already
preserves the section headers needed to detect this structurally — this is the highest-leverage
single fix and is low-effort because the structural signal already exists.

**Acceptance check when done:** Re-run the exact two verification queries above; confirm no
reference-list chunk ranks above a content chunk, and query 2's #1 result is a findings
chunk, not a bibliography.

### Item 2 — Citation-density re-ranker (CONTINGENCY ONLY)

**Necessity:** Probably never necessary. This is the fallback if Item 1 proves insufficient.
Do NOT plan this as work; activate only if Item 1 ships and reference-list noise persists.

**Approach (if ever needed):** A light re-ranking penalty for chunks that are mostly
citations — high density of years, "et al.", DOI/arXiv strings, bracketed reference markers.
More general than Item 1 but more work, and redundant if Item 1 works.

## Also worth confirming (not a fix — a question)

Every citation in both verification queries showed `claim_count: 1`. The 3-paper validation
reported 373 claims over 3 papers (~124/paper). Confirm with architect what `claim_count`
in `research-query` output represents — "claims matching this query" (fine) vs "total claims
for this paper" (would indicate claim extraction is shallower than believed). One-line
clarification, not necessarily a fix.

## Activation triggers

Promote Item 1 from this backlog to a work packet when ANY of:
- Director decides to move academic pipeline from demo-ready → production-ready
- Corpus grows past ~50 papers (reference-noise fraction climbs)
- A non-coder operator path / UI is being built (answer quality becomes user-facing)
- Operator simply wants to clear it during a low-priority window

Until then: parked, optional, non-blocking.

## Cross-references

- [[claude-memory/work-packets/work-packet-academic-pipeline-scaled-validation-corpus]] — the closed validation packet whose corpus this was tested against
- [[claude-memory/work-packets/work-packet-paperqa2-rag-control-flow]] — L2 / L2.1 retrieval, where the ranking lives
- [[ris-mirror/external_knowledge/acad-a1921b9a-the-anatomy-of-a-decentralized-prediction-market-microstruct|test paper: Anatomy of a Decentralized Prediction Market]]
