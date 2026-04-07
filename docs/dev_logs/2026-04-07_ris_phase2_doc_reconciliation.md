# Dev Log: RIS Phase 2 Documentation Contract Freeze (v1.1)

**Date:** 2026-04-07
**Task:** Freeze RIS Phase 2 documentation contract before implementation
**Scope:** DOCS-ONLY — no code, no workflows, no schemas, no migrations

## What Was Done

Bumped the RIS roadmap suite from v1.0 to v1.1, incorporating ten Director-accepted
additions into the canonical specification documents. Reconciled PLAN_OF_RECORD.md
LLM policy to authorize Tier 1 free APIs for RIS evaluation.

## Files Edited

| File | Change |
|------|--------|
| `docs/PLAN_OF_RECORD.md` | Added narrow Tier 1 free-API exception for RIS evaluation in LLM/signals row |
| `docs/reference/RAGfiles/RIS_OVERVIEW.md` | Bumped to v1.1, added Changelog, Posture Statement, v1.1 note in Development Phases |
| `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md` | Added: fail-closed rule, weighted composite gate, canonical-ID dedup pre-step, review queue contract (pending_review table), per-priority acceptance gates |
| `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` | Added: ingestion budget controls (global/per-source/manual-reserve), n8n env-var-primary config hierarchy, ClickHouse write idempotency (execution_id + ReplacingMergeTree + prefilter) |

## Additions Included (all 10)

1. Fail-closed evaluation rule
2. Weighted composite gate (relevance=0.30, novelty=0.25, actionability=0.25, credibility=0.20) + per-dimension floor (relevance>=2, credibility>=2); simple sum /20 retained as diagnostic only
3. Novelty dedup by canonical doc_id / source_url before embedding similarity check
4. Review queue contract: KnowledgeStore SQLite pending_review table + CLI research-review flow
5. Budget controls: global daily cap (200), per-source caps, manual-reserve hold-back (10)
6. Explicit per-priority acceptance gates (Critical>=2.5, High>=3.0, Medium>=3.2, Low>=3.5)
7. Segmented retrieval benchmark metrics by query class (factual, analytical, exploratory) — noted in changelog; detailed spec deferred to RIS_05 update
8. n8n env-var fallback as primary config source; Variables optional convenience only
9. ClickHouse idempotency: execution_id + ReplacingMergeTree + code-level prefilter
10. Research-only posture statement added to RIS_OVERVIEW

## PLAN_OF_RECORD Reconciliation

The LLM/signals row previously read: "no external LLM API calls."
This conflicted with the Master Roadmap v5.1 LLM Policy table which explicitly lists
Tier 1 free cloud APIs (DeepSeek V3, Gemini Flash) for automated evaluation.

Resolution: appended a single-sentence exception scoped to RIS evaluation gate scoring only.
The exception does not authorize Tier 1 APIs for trading signals, order placement, or
any non-RIS use case. This aligns PLAN_OF_RECORD with the already-governing Master Roadmap v5.1.

## Cross-Reference Conflict Check

- `docs/ARCHITECTURE.md` — No conflict. Architecture doc defers to Master Roadmap v5.1 for
  LLM policy; does not repeat the "no external LLM API calls" restriction.
- `CLAUDE.md` — No conflict. References PLAN_OF_RECORD as authoritative. The "no external
  LLM API calls" text in CLAUDE.md's constraints section refers to "shipped outputs" and
  "trading recommendations", not to RIS evaluation scoring.
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` — No conflict. v5.1 already authorizes
  Tier 1 free APIs for "scraper evaluation" and "signal classification."

## What Was NOT Done

- No code changes. No workflow JSON. No tests. No Docker config. No schema migrations.
- RIS_05 (Synthesis Engine) was NOT edited. Item 7 (segmented benchmark by query class)
  is noted in the v1.1 changelog but the detailed spec belongs in RIS_05; that file will
  be updated when implementation planning for the synthesis engine begins.
- No changes to RIS_01, RIS_02, RIS_04, or RIS_07 companion files.
- No broadening of LLM policy beyond RIS evaluation.

## Codex Review

Tier: Skip (docs-only change set, no code files modified).

## Open Questions

None. All ten additions are now frozen in the canonical docs. Implementation can proceed
against this v1.1 contract.
