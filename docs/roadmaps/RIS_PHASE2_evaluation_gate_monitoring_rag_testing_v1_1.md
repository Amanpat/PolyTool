# RIS Phase 2 Roadmap — Evaluation Gate, Monitoring, RAG Testing (v1.1 Contract)

**Status:** Pending Implementation  
**Derived from:** RIS_OVERVIEW.md v1.1 (April 2026) + Director-approved additions frozen by quick-260407-lpr  
**Last updated:** 2026-04-07

---

## Purpose

This document is the canonical in-repo task source for RIS Phase 2 implementation work.
It consolidates the 10 Director-approved contract items from the RIS_OVERVIEW.md v1.1
changelog into an actionable checklist with spec cross-references.

This is a TASK-ORIENTED roadmap — what to build and in what order. It does not
restate full specifications; it cross-references them.

### Cross-References

| Document | Role |
|----------|------|
| `docs/reference/RAGfiles/RIS_OVERVIEW.md` | Master system spec (v1.1) — start here |
| `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md` | Gate implementation details (items 1-4, 6-7) |
| `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` | Infrastructure details (items 5, 8-9) |
| `docs/PLAN_OF_RECORD.md` Section 0 | LLM policy — governs cloud provider authorization |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | ADR for n8n pilot scope (item 8) |

---

## LLM Policy Status

**Narrow exception granted (quick-260407-lpr):**  
Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) are authorized for RIS evaluation
gate scoring ONLY. This exception is documented in PLAN_OF_RECORD Section 0.

**Authority chain:**
1. Master Roadmap v5.1 — broadest authorization (Tier 1 free cloud APIs for RIS)
2. PLAN_OF_RECORD Section 0 — narrows scope to evaluation gate scoring only
3. RIS_OVERVIEW v1.1 + RIS_03 + RIS_06 — spec details for implementation
4. This roadmap doc — task checklist derived from specs above

**Implementation reality (as of 2026-04-07):**
- Cloud providers are NOT yet implemented in code.
- `packages/research/evaluation/providers.py` (or equivalent) has `manual` and `ollama` only.
- `RIS_ENABLE_CLOUD_PROVIDERS` environment variable has no effect — no cloud code exists yet.
- `config/ris_eval_config.json` does not exist yet.
- No code changes in this roadmap alter the above — these are prerequisites for item 1 execution.

---

## Scheduling Status

**Default scheduler:** APScheduler (already in the Python stack, active in production).

**n8n status:** Scoped opt-in RIS pilot ONLY (ADR-0013). Activated via `--profile ris-n8n`.
n8n is NOT the default orchestrator for the project. Broad n8n orchestration remains a
Phase 3 target. For RIS scheduling work, default to APScheduler unless the task
explicitly scopes to the n8n pilot path.

---

## Phase 2 Contract Items

All 10 items below were accepted by Director before implementation in the v1.1 changelog.
Each item is a `- [ ]` to track completion. Items are ordered by dependency, not priority.

### Evaluation Gate Items (packages/research/evaluation/)

- [x] **1. Fail-closed evaluation rule** — If LLM scoring is unavailable (network error,
  API quota exceeded, provider not configured), the document queues for retry and defaults
  to REJECT. Never auto-accepts on scoring failure. No silent pass-through.
  _Spec: RIS_03 Section "Fail-Closed Rule"_

- [x] **2. Weighted composite quality gate** — Replace single-score LLM output with a
  multi-factor weighted composite: relevance=0.30, novelty=0.25, actionability=0.25,
  credibility=0.20. Per-dimension floor of 2 on relevance and credibility. Simple sum
  retained as diagnostic output only.
  _Spec: RIS_03 Section "Weighted Composite Gate"_

- [x] **3. Novelty/dedup detection** — Before injecting document into the evaluation
  prompt, run canonical-ID deduplication (doc_id / source_url) and nearest-neighbor
  embedding similarity check. Deduplicate first; evaluate only novel content.
  _Spec: RIS_03 Section "Canonical-ID Dedup Pre-Step"_

- [x] **4. Review queue contract** — YELLOW-zone documents (score 8-12) are queued to a
  `pending_review` table in the KnowledgeStore SQLite. CLI `research-review` flow allows
  operator to promote or reject queued items. 72-hour auto-promote or auto-reject policy
  applies if operator does not respond.
  _Spec: RIS_03 Section "Review Queue Contract"; RIS_04_KNOWLEDGE_STORE.md_
  _(Caveat: queue storage + CLI complete; 72-hour auto-expiry policy not yet implemented)_

- [x] **6. Per-priority acceptance gates** — Different GREEN/YELLOW/RED thresholds apply
  per source priority tier. High-priority sources (e.g., operator-submitted URLs) use
  lower rejection thresholds than low-priority automated pipeline sources.
  _Spec: RIS_03 Section "Per-Priority Acceptance Gates"_

- [x] **7. Segmented benchmark metrics** — Evaluation accuracy tracked and reported
  separately per source type (academic, social, manual) and per priority tier. Benchmark
  metrics reported by query class: factual, analytical, exploratory.
  _Spec: RIS_03_EVALUATION_GATE.md and RIS_05_SYNTHESIS_ENGINE.md_

### Ingestion Layer Items (packages/research/ingestion/)

- [ ] **5. Per-source daily budget caps** — Global daily cap of 200 documents/day enforced.
  Per-source daily limits configurable. Manual-reserve hold-back of 10 slots/day for
  operator-submitted URLs. Budget state persisted across restarts.
  _Spec: RIS_06 Section "Ingestion Budget Controls"_

### Infrastructure / Persistence Items

- [x] **8. Env-var-primary n8n config hierarchy** — When using the n8n RIS pilot
  (`--profile ris-n8n`), `process.env.RIS_*` environment variables are the primary
  source of truth for configuration. n8n Variables are optional convenience overrides
  only. Code must not require n8n Variables to be set.
  _Spec: RIS_06 Section "n8n Configuration Hierarchy"; ADR-0013_

- [x] **9. Dual-layer ClickHouse write idempotency** — ClickHouse `ris_events` and related
  tables use ReplacingMergeTree engine for storage-level idempotency. Code-level prefilter
  checks `execution_id` before issuing INSERT. Both layers required.
  _Spec: RIS_06 Section "ClickHouse Write Idempotency"_
  _(N/A -- RIS uses SQLite via KnowledgeStore, not ClickHouse; no ris_events table exists; SQLite doc_id uniqueness provides storage-level idempotency)_

### Documentation Guard Rail

- [ ] **10. Research-only posture statement** — All RIS output surfaces (reports, precheck
  verdicts, knowledge-base entries) must carry or reference the posture statement: RIS
  outputs are research context, not trading signals. Risk and execution decisions remain
  human-only. This statement is already in RIS_OVERVIEW v1.1; the task is to verify all
  CLI output and report templates reference or include it.
  _Spec: RIS_OVERVIEW Section "Posture Statement"_

---

## Implementation Notes

### Grouping by target package

| Package area | Contract items |
|---|---|
| `packages/research/evaluation/` | Items 1, 2, 3, 4, 6, 7 |
| `packages/research/ingestion/` | Item 5 |
| ClickHouse write paths + n8n config | Items 8, 9 |
| Documentation / CLI output templates | Item 10 |

### What this plan does NOT touch

- No changes to SimTrader, execution layer, gates (Gate 2/Gate 3), or live trading.
- No changes to benchmark manifests or benchmark closure artifacts.
- No changes to existing APScheduler scheduling for non-RIS workflows.
- No changes to Chroma partition structure or BGE-M3 embedding configuration.
- Cloud provider implementation (Gemini Flash, DeepSeek V3) is a prerequisite for items
  1-4, 6-7 but is NOT part of this Phase 2 checklist — it is tracked separately as an
  infrastructure prerequisite that unlocks Phase 2 execution.

### Recommended execution order

1. Item 3 (dedup detection) — prerequisite for items 1 and 2
2. Items 1 + 2 (fail-closed + weighted composite) — core gate logic, implement together
3. Item 4 (review queue) — depends on gate producing YELLOW-zone outputs
4. Item 5 (budget caps) — independent, can be parallelized with items 1-3
5. Items 6 + 7 (per-priority gates + segmented metrics) — build after core gate is stable
6. Item 9 (ClickHouse idempotency) — infrastructure, independent
7. Item 8 (n8n config hierarchy) — only relevant if n8n pilot path is active
8. Item 10 (posture statement audit) — documentation sweep after functional items complete

---

*Derived from RIS_OVERVIEW.md v1.1 — Director-approved contract frozen by quick-260407-lpr.*  
*For full specifications see companion files RIS_03_EVALUATION_GATE.md, RIS_06_INFRASTRUCTURE.md.*
