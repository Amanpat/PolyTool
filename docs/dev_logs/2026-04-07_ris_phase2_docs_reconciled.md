# RIS Phase 2 Docs Reconciliation

**Date:** 2026-04-07  
**Work unit:** quick-260407-pbi  
**Depends on:** quick-260407-lpr (v1.1 contract freeze in RIS spec docs)  
**Codex review:** Skip — docs-only change set, no code modified.

---

## What Changed

### 1. Created `docs/roadmaps/` directory (new)

This directory did not exist. Created to hold canonical phase/feature roadmap docs
that are task-oriented checklists, distinct from specs (`docs/specs/`) and feature
descriptions (`docs/features/`).

### 2. Created `docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md`

Canonical Phase 2 roadmap consolidating all 10 Director-approved contract items from
RIS_OVERVIEW v1.1 into an actionable checklist with spec cross-references.

The 10 items (all `- [ ]`) are:
1. Fail-closed evaluation rule
2. Weighted composite quality gate
3. Novelty/dedup detection
4. Review queue contract (72-hour auto-promote/auto-reject)
5. Per-source daily budget caps (200/day global, per-source limits, 10-slot manual reserve)
6. Per-priority acceptance gates
7. Segmented benchmark metrics
8. Env-var-primary n8n config hierarchy
9. Dual-layer ClickHouse write idempotency
10. Research-only posture statement verification

Document includes:
- LLM Policy Status section: narrow exception granted (Gemini Flash, DeepSeek V3 for
  eval gate scoring only, per PLAN_OF_RECORD Section 0); cloud providers NOT yet in code.
- Scheduling Status section: APScheduler is default; n8n is scoped opt-in pilot (ADR-0013).
- Implementation Notes: target packages per item, execution order recommendation.

### 3. Patched `docs/CURRENT_STATE.md` line 5

**Before:**
```
RAG workflow that never calls external LLM APIs.
```

**After:**
```
RAG workflow that defaults to local-only LLM inference. (Narrow exception: Tier 1
free cloud APIs are authorized for RIS evaluation gate scoring only — see
PLAN_OF_RECORD Section 0 and quick-260407-lpr.)
```

This fixes the stale absolute "never" claim. The local-first posture is preserved;
the narrow exception is now accurately represented.

### 4. Patched `docs/CURRENT_STATE.md` lines 794-799 (authority conflict block)

**Before:**
```
**Authority conflict (unresolved):** Roadmap v5.1 LLM Policy allows Tier 1 free
cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash). PLAN_OF_RECORD Section 0 states
"Current toolchain policy remains no external LLM API calls." The knowledge store
includes a provider abstraction (`_llm_provider`) but cloud execution is disabled
by default. Operator decision required before enabling cloud LLM calls for claim
extraction or scraper evaluation.
```

**After:**
```
**Authority conflict (RESOLVED, quick-260407-lpr):** PLAN_OF_RECORD Section 0 now
carries a narrow exception: Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) are
authorized for RIS evaluation gate scoring only. Cloud providers are NOT yet
implemented in code (`providers.py` has `manual` and `ollama` only;
`RIS_ENABLE_CLOUD_PROVIDERS` env var has no effect). The knowledge store provider
abstraction (`_llm_provider`) is wired but cloud execution remains disabled until
the provider implementations ship.
```

---

## What Did NOT Change (Scope Guard)

- No code, tests, config files, workflow JSON, or schemas modified.
- `docs/PLAN_OF_RECORD.md` — already correct; patched by quick-260407-lpr.
- `docs/RIS_OPERATOR_GUIDE.md` — already correctly states cloud providers don't work yet.
- `docs/ARCHITECTURE.md` — no LLM policy text to update.
- `docs/reference/RAGfiles/RIS_OVERVIEW.md` — spec doc at v1.1, frozen by quick-260407-lpr.
- `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md` — spec doc, frozen.
- `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` — spec doc, frozen.

---

## Remaining Work (Not in Scope of This Task)

The following are prerequisites or follow-on work, not part of this docs-reconciliation unit:

- Implement cloud provider classes in `providers.py` (Gemini Flash, DeepSeek V3).
- Create `config/ris_eval_config.json`.
- Make `RIS_ENABLE_CLOUD_PROVIDERS` env var functional.
- Execute Phase 2 contract items 1-10 per the new roadmap doc.

---

## Authority Chain (Resolved State)

1. Master Roadmap v5.1 — broadest LLM authorization (Tier 1 free cloud APIs for RIS)
2. PLAN_OF_RECORD Section 0 — narrows to RIS evaluation gate scoring only (quick-260407-lpr)
3. RIS_OVERVIEW v1.1 + RIS_03 + RIS_06 — spec details per contract item
4. `docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md` — task
   checklist derived from specs; canonical in-repo Phase 2 task source
