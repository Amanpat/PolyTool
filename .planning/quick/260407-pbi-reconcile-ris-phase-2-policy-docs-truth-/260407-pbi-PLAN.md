---
phase: quick-260407-pbi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md
autonomous: true
requirements: [DOCS-ONLY]
must_haves:
  truths:
    - "A canonical RIS Phase 2 roadmap doc exists under docs/roadmaps/"
    - "CURRENT_STATE.md no longer contains stale 'never calls external LLM APIs' without qualification"
    - "CURRENT_STATE.md no longer says 'Authority conflict (unresolved)' for the LLM policy"
    - "A dev log captures every delta made in this work unit"
  artifacts:
    - path: "docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md"
      provides: "Canonical in-repo Phase 2 roadmap with all 10 Director-approved items"
      min_lines: 80
    - path: "docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md"
      provides: "Dev log documenting exact deltas"
      min_lines: 20
  key_links:
    - from: "docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md"
      to: "docs/reference/RAGfiles/RIS_OVERVIEW.md"
      via: "cross-reference to v1.1 spec"
      pattern: "RIS_OVERVIEW"
    - from: "docs/CURRENT_STATE.md"
      to: "docs/PLAN_OF_RECORD.md"
      via: "references PLAN_OF_RECORD Section 0 narrow exception"
      pattern: "PLAN_OF_RECORD.*Section 0"
---

<objective>
Reconcile RIS Phase 2 policy docs truth and create a canonical in-repo Phase 2 roadmap source.

Purpose: After quick-260407-lpr froze the v1.1 contract in RIS spec docs and patched
PLAN_OF_RECORD Section 0 with the narrow LLM exception, several downstream docs still
contain stale or contradictory text. Additionally, no standalone Phase 2 roadmap doc
exists — the 10 Director-approved items live only inside spec files (RIS_03, RIS_06,
RIS_OVERVIEW). This plan creates the canonical roadmap doc and patches the remaining
stale text so all authority docs agree.

Output: One new roadmap doc, patched CURRENT_STATE.md, and a dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/CURRENT_STATE.md
@docs/reference/RAGfiles/RIS_OVERVIEW.md
@docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md
@docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/adr/0013-ris-n8n-pilot-scoped.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create canonical RIS Phase 2 roadmap doc</name>
  <files>docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md</files>
  <action>
Create the directory `docs/roadmaps/` if it does not exist.

Write the canonical RIS Phase 2 roadmap document. This is a TASK-ORIENTED roadmap (what
to build in what order), NOT a spec re-statement. It consolidates the 10 Director-approved
Phase 2 contract items from RIS_OVERVIEW.md v1.1 changelog into an actionable checklist.

Structure the document as follows:

**Header section:**
- Title: "RIS Phase 2 Roadmap — Evaluation Gate, Monitoring, RAG Testing (v1.1 Contract)"
- Purpose statement: canonical in-repo Phase 2 task source; derived from RIS_OVERVIEW.md v1.1
  and Director-approved additions frozen by quick-260407-lpr.
- Cross-references: RIS_OVERVIEW.md (spec), RIS_03_EVALUATION_GATE.md (gate details),
  RIS_06_INFRASTRUCTURE.md (infra details), PLAN_OF_RECORD.md Section 0 (LLM policy exception).

**LLM Policy Status section:**
State clearly:
- Narrow exception granted: Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) authorized
  for RIS evaluation gate scoring ONLY (per PLAN_OF_RECORD Section 0, quick-260407-lpr).
- Master Roadmap v5.1 authorizes broader scope but PLAN_OF_RECORD narrows it.
- Cloud providers NOT yet implemented in code — `providers.py` only has `manual` and `ollama`.
  `RIS_ENABLE_CLOUD_PROVIDERS` env var has no effect.
- `config/ris_eval_config.json` does not exist yet.

**Scheduling Status section:**
State clearly:
- APScheduler is the default scheduler (already in Python stack).
- n8n is a scoped opt-in RIS pilot only (ADR-0013), activated via `--profile ris-n8n`.
- n8n is NOT the default orchestrator. Broad n8n orchestration is a Phase 3 target.

**Phase 2 Contract Items checklist (10 items, each as `- [ ]`):**

1. Fail-closed evaluation rule — if LLM unavailable, document queues for retry; never
   auto-accepts. (Spec: RIS_03 Section "Fail-Closed Rule")
2. Weighted composite quality gate — multi-factor scoring replacing single LLM score.
   (Spec: RIS_03 Section "Weighted Composite Gate")
3. Novelty/dedup detection — canonical-ID pre-step before evaluation.
   (Spec: RIS_03 Section "Canonical-ID Dedup Pre-Step")
4. Review queue contract — YELLOW-zone items queue for operator review with 72-hour
   auto-promote/auto-reject policy. (Spec: RIS_03 Section "Review Queue Contract")
5. Per-source daily budget caps — global 200/day, per-source limits, manual reserve of 10.
   (Spec: RIS_06 Section "Ingestion Budget Controls")
6. Per-priority acceptance gates — different acceptance thresholds by priority tier.
   (Spec: RIS_03 Section "Per-Priority Acceptance Gates")
7. Segmented benchmark metrics — evaluation accuracy tracked per source type and priority.
   (Spec: RIS_03)
8. Env-var-primary n8n config hierarchy — `process.env.RIS_*` is source of truth, n8n
   Variables are optional convenience. (Spec: RIS_06 Section "n8n Configuration Hierarchy")
9. Dual-layer ClickHouse write idempotency — ReplacingMergeTree + code-level prefilter
   on `execution_id`. (Spec: RIS_06 Section "ClickHouse Write Idempotency")
10. Research-only posture statement — RIS outputs are research context, not trading signals.
    Risk/execution decisions remain human-only. (Spec: RIS_OVERVIEW Section "Posture Statement")

**Implementation Notes section:**
- Items 1-4 and 6-7 are evaluation-gate work (packages/research/evaluation/).
- Item 5 is ingestion-layer budget enforcement (packages/research/ingestion/).
- Items 8-9 are infrastructure/persistence (ClickHouse write paths, n8n config).
- Item 10 is a documentation guard rail (already stated in RIS_OVERVIEW v1.1).
- No item requires code changes to SimTrader, execution, gates, or live trading.

**DO NOT** include any implementation code. This is a roadmap doc, not a spec.
**DO NOT** copy-paste full spec sections — cross-reference them.
  </action>
  <verify>
    <automated>test -d "docs/roadmaps" && test -f "docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md" && wc -l "docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md" | awk '{if ($1 >= 80) print "PASS"; else print "FAIL: only " $1 " lines"}'</automated>
  </verify>
  <done>
    docs/roadmaps/ directory exists. Roadmap doc has 80+ lines. All 10 contract items
    present as checklist entries. LLM policy status and scheduling status sections present.
    Cross-references to RIS_OVERVIEW, RIS_03, RIS_06, PLAN_OF_RECORD, and ADR-0013 present.
  </done>
</task>

<task type="auto">
  <name>Task 2: Patch CURRENT_STATE.md to resolve stale authority conflict text</name>
  <files>docs/CURRENT_STATE.md</files>
  <action>
Make exactly TWO targeted edits to docs/CURRENT_STATE.md. No other changes.

**Edit 1 — Line 4 (opening description):**
Current text (line 4):
```
RAG workflow that never calls external LLM APIs.
```
Replace with:
```
RAG workflow that defaults to local-only LLM inference. (Narrow exception: Tier 1
free cloud APIs are authorized for RIS evaluation gate scoring only — see
PLAN_OF_RECORD Section 0 and quick-260407-lpr.)
```
This fixes the stale absolute "never" claim while preserving the local-first posture.

**Edit 2 — Lines 794-799 (authority conflict block):**
Current text:
```
**Authority conflict (unresolved):** Roadmap v5.1 LLM Policy allows Tier 1 free
cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash). PLAN_OF_RECORD Section 0 states
"Current toolchain policy remains no external LLM API calls." The knowledge store
includes a provider abstraction (`_llm_provider`) but cloud execution is disabled
by default. Operator decision required before enabling cloud LLM calls for claim
extraction or scraper evaluation.
```
Replace with:
```
**Authority conflict (RESOLVED, quick-260407-lpr):** PLAN_OF_RECORD Section 0 now
carries a narrow exception: Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) are
authorized for RIS evaluation gate scoring only. Cloud providers are NOT yet
implemented in code (`providers.py` has `manual` and `ollama` only;
`RIS_ENABLE_CLOUD_PROVIDERS` env var has no effect). The knowledge store provider
abstraction (`_llm_provider`) is wired but cloud execution remains disabled until
the provider implementations ship.
```

**DO NOT** touch any other lines, sections, or content in CURRENT_STATE.md.
**DO NOT** add new sections, move sections, or reformat existing content.
  </action>
  <verify>
    <automated>grep -c "Authority conflict (RESOLVED" docs/CURRENT_STATE.md | awk '{if ($1 >= 1) print "PASS: conflict marked resolved"; else print "FAIL: conflict not marked resolved"}' && grep -c "never calls external LLM APIs" docs/CURRENT_STATE.md | awk '{if ($1 == 0) print "PASS: stale never-claim removed"; else print "FAIL: stale never-claim still present"}'</automated>
  </verify>
  <done>
    Line 4 no longer says "never calls external LLM APIs" — says "defaults to local-only"
    with narrow exception noted. Lines 794-799 say "RESOLVED" instead of "unresolved" and
    reference quick-260407-lpr. No other lines changed.
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log documenting exact deltas</name>
  <files>docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md</files>
  <action>
Create the dev log at `docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md`.

Structure:

**Title:** "RIS Phase 2 Docs Reconciliation"
**Date:** 2026-04-07
**Depends on:** quick-260407-lpr (v1.1 contract freeze in RIS spec docs)

**What changed:**
1. Created `docs/roadmaps/` directory (new).
2. Created `docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md` —
   canonical Phase 2 roadmap consolidating all 10 Director-approved contract items from
   RIS_OVERVIEW v1.1 into an actionable checklist with cross-references.
3. Patched `docs/CURRENT_STATE.md` line 4: "never calls external LLM APIs" replaced with
   "defaults to local-only LLM inference" plus narrow exception caveat.
4. Patched `docs/CURRENT_STATE.md` lines 794-799: "Authority conflict (unresolved)" replaced
   with "Authority conflict (RESOLVED, quick-260407-lpr)" with implementation status note.

**What did NOT change (scope guard):**
- No code, tests, config files, or workflow JSON modified.
- `docs/PLAN_OF_RECORD.md` — already correct (patched by quick-260407-lpr).
- `docs/RIS_OPERATOR_GUIDE.md` — already correctly states cloud providers don't work yet.
- `docs/ARCHITECTURE.md` — no LLM policy text to update.
- `docs/reference/RAGfiles/*` — spec docs already at v1.1 (frozen by quick-260407-lpr).

**Remaining work (not in scope of this task):**
- Implement cloud provider classes in `providers.py` (Gemini Flash, DeepSeek V3).
- Create `config/ris_eval_config.json`.
- Execute Phase 2 contract items per the new roadmap doc.

**Authority chain:**
- Master Roadmap v5.1 (broadest LLM authorization)
- PLAN_OF_RECORD Section 0 (narrows to RIS eval gate scoring only)
- RIS_OVERVIEW v1.1 + RIS_03 + RIS_06 (spec details)
- This roadmap doc (task checklist derived from specs)
  </action>
  <verify>
    <automated>test -f "docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md" && grep -c "quick-260407-lpr" "docs/dev_logs/2026-04-07_ris_phase2_docs_reconciled.md" | awk '{if ($1 >= 1) print "PASS"; else print "FAIL: missing lpr reference"}'</automated>
  </verify>
  <done>
    Dev log exists, references quick-260407-lpr dependency, lists all 4 deltas, lists
    scope-guard exclusions, and notes remaining work.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply — this is a DOCS-ONLY plan with no code, config, or
runtime changes.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-pbi-01 | Tampering | docs/CURRENT_STATE.md | accept | Docs-only edit to 2 specific lines; git diff reviewable; no runtime impact |
| T-pbi-02 | Information Disclosure | roadmap doc | accept | Roadmap describes planned work, not secrets; repo is private |
</threat_model>

<verification>
1. `docs/roadmaps/` directory exists
2. Roadmap doc contains all 10 contract items as checklist entries
3. CURRENT_STATE.md line 4 no longer says "never calls external LLM APIs"
4. CURRENT_STATE.md authority conflict marked RESOLVED
5. Dev log exists with all deltas documented
6. No code, test, config, or workflow JSON files modified
</verification>

<success_criteria>
- Canonical RIS Phase 2 roadmap doc exists at docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
- All 10 Director-approved contract items appear as checklist items with spec cross-references
- CURRENT_STATE.md authority docs are consistent with PLAN_OF_RECORD Section 0
- Dev log captures every delta
- Zero code changes
</success_criteria>

<output>
After completion, create `.planning/quick/260407-pbi-reconcile-ris-phase-2-policy-docs-truth-/260407-pbi-SUMMARY.md`
</output>
