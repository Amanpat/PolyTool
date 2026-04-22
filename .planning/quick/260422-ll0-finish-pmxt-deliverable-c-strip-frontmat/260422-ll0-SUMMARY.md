---
phase: quick
plan: 260422-ll0
subsystem: ris
tags: [ris, retriever, knowledge-store, deliverable-c, gap-fix]
key-decisions:
  - "When text_query is provided to query_knowledge_store_for_rrf, pass top_k=None to the enriched fetch so the substring filter operates over all claims, not just the top_k*4 cap."
  - "query_knowledge_store_enriched top_k changed to Optional[int]; None guard added to loop break condition."
metrics:
  completed: "2026-04-22"
  tasks: 4
  files_changed: 4
---

# Quick Task 260422-ll0: Deliverable C Gap1 Fix — Summary

## One-liner

Retriever over-fetch truncation fixed (top_k=None when text_query set); 2/5 original queries now surface external_knowledge body claims, meeting the >=2/5 Deliverable C threshold.

## Deliverable C Final Status: COMPLETE

The 2/5 body-driven hit threshold was met after fixing Gap 1.

| Query | Body-claim in top 5? |
|-------|----------------------|
| Q1: "Polymarket maker rebate formula" | No |
| Q2: "sports VWAP prediction market" | No |
| Q3: "SimTrader queue position" | **Yes — rank 2, external_knowledge** |
| Q4: "Jaccard Levenshtein market matching" | **Yes — rank 2, external_knowledge** |
| Q5: "cross-platform price divergence" | No (frontmatter-claim only) |

**2/5 body-driven. Threshold >=2/5. COMPLETE.**

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| A | Fix Gap 1 in retriever.py (over-fetch truncation) | 0efd895 |
| B | Rerun 5 official queries, classify top-5 | 0efd895 |
| C | Write dev log 2026-04-22_deliverable-c_gap1-fix.md | 0efd895 |
| D | Truth-sync CURRENT_DEVELOPMENT.md | 0efd895 |

## Dev Log

`docs/dev_logs/2026-04-22_deliverable-c_gap1-fix.md`

## Commit

`0efd895` — fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix

## Remaining Provisional Docs

The following docs retain their `source_quality_caution: SECONDARY_SYNTHESIS` blocks
and are explicitly provisional. No edits made to them:

- `docs/external_knowledge/cross_platform_price_divergence_empirics.md`
- `docs/external_knowledge/cross_platform_market_matching.md`

Q5's knowledge_store hit comes from `cross_platform_price_divergence_empirics.md`
and is classified as a frontmatter-claim (not body-claim). Q4's body-claim hit
comes from `cross_platform_market_matching.md` (the claim is a synthesized sentence;
caution block preserved).

## Self-Check

- [x] retriever.py fix committed (0efd895)
- [x] regression test passes (64/64)
- [x] dev log created at docs/dev_logs/2026-04-22_deliverable-c_gap1-fix.md
- [x] CURRENT_DEVELOPMENT.md updated (table row + Notes section)
- [x] only scoped files committed (no git add -A)
- [x] 2/5 threshold confirmed from live query output
