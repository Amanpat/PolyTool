---
phase: 260409-jfm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/features/FEATURE-ris-phase2-closeout.md
  - docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md
  - docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
autonomous: true
requirements: [phase2-closeout]
must_haves:
  truths:
    - "Every Phase 2 contract item (1-10) has a clear pass/fail/N-A disposition with evidence"
    - "Remaining caveats are explicit and not hidden"
    - "Final recommendation (complete or blocked) is evidence-backed"
  artifacts:
    - path: "docs/features/FEATURE-ris-phase2-closeout.md"
      provides: "Phase 2 acceptance artifact with per-item disposition"
    - path: "docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md"
      provides: "Dev log with commands run and evidence trail"
  key_links:
    - from: "docs/features/FEATURE-ris-phase2-closeout.md"
      to: "docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md"
      via: "Roadmap checkbox status updated if closeout passes"
      pattern: "\\[x\\]"
---

<objective>
Produce a Phase 2 RIS acceptance sweep and closeout artifact. The plan builds a concise
acceptance checklist from the Phase 2 roadmap (10 contract items), verifies each with
targeted test runs and CLI evidence, writes the closeout doc and dev log, and updates the
roadmap checklist only if evidence supports completion.

Purpose: Phase 2 has accumulated 6+ dev logs of implementation work across 2026-04-08.
This plan consolidates all evidence into one acceptance artifact so the operator can
decide whether to mark Phase 2 complete.

Output: closeout doc, dev log, and (conditionally) roadmap status update.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
@docs/specs/SPEC-ris-phase2-operational-contracts.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/dev_logs/2026-04-08_ris_phase2_eval_gate_core.md
@docs/dev_logs/2026-04-08_ris_phase2_cloud_provider_routing.md
@docs/dev_logs/2026-04-08_ris_phase2_ingest_review_integration.md
@docs/dev_logs/2026-04-08_ris_phase2_review_queue_cli.md
@docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
@docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md
@docs/dev_logs/2026-04-08_unified_n8n_alerts_and_summary.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run targeted verification commands and collect evidence</name>
  <files>docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md</files>
  <action>
Run the following verification commands and record exact output. These are READ-ONLY
verification commands -- do NOT modify any code or tests.

**1. Run the focused RIS Phase 2 test suite (all Phase 2 test files):**
```
rtk python -m pytest tests/test_ris_phase2_weighted_gate.py tests/test_ris_phase2_cloud_provider_routing.py tests/test_ris_evaluation.py tests/test_ris_ingestion_integration.py tests/test_ris_review_queue.py tests/test_ris_monitoring.py tests/test_ris_research_acquire_cli.py tests/test_ris_phase5_provider_enablement.py tests/test_rag_eval.py -q
```

**2. Verify research-health CLI loads and runs:**
```
python -m polytool research-health --json
```

**3. Verify research-stats summary CLI:**
```
python -m polytool research-stats summary --json
```

**4. Verify research-review CLI presence:**
```
python -m polytool research-review --help
```

**5. Verify research-eval CLI with provider listing:**
```
python -m polytool research-eval --help
```

**6. Verify ris_eval_config.json exists and is valid JSON:**
```
python -m json.tool config/ris_eval_config.json > /dev/null && echo "VALID JSON"
```

**7. Verify retrieval benchmark suite exists:**
```
python -m json.tool docs/eval/ris_retrieval_benchmark.jsonl --no-fuss 2>/dev/null || python -c "import json; [json.loads(l) for l in open('docs/eval/ris_retrieval_benchmark.jsonl')]; print('VALID JSONL')"
```

**8. Check for budget cap implementation evidence:**
```
grep -rn "budget\|daily_cap\|per_source.*cap\|budget_exhausted" packages/research/ingestion/ packages/research/evaluation/ packages/research/scheduling/ --include="*.py" | head -30
```

**9. Check for posture statement in CLI outputs:**
```
grep -rn "research context\|not trading signals\|research-only\|posture" tools/cli/research_*.py packages/research/evaluation/scoring.py packages/research/synthesis/ --include="*.py" | head -20
```

**10. Check ClickHouse RIS table existence (code-level, not runtime):**
```
grep -rn "ris_events\|ReplacingMergeTree.*ris\|execution_id.*INSERT" packages/ tools/ --include="*.py" | head -10
```

Record ALL output in the dev log with the exact checklist structure below:

```markdown
## Phase 2 Contract Item Evidence

### Item 1: Fail-closed evaluation
- Tests: [pass count from step 1]
- Dev log evidence: 2026-04-08_ris_phase2_eval_gate_core.md
- Status: PASS / FAIL / CAVEAT

### Item 2: Weighted composite gate
[etc for all 10 items]
```

For Item 5 (budget caps) and Item 9 (ClickHouse idempotency), if grep finds no
implementation evidence, record honestly as NOT IMPLEMENTED with the specific grep
output showing absence. Do NOT claim these are implemented without code evidence.

For Item 10 (posture statement), record what grep finds. If the posture statement
appears in the scoring prompt template or synthesis output but not in every CLI
surface, note the gap precisely.

Write the dev log to docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md with:
- All commands run and their exact summarized output
- Per-item evidence table
- Final recommendation
  </action>
  <verify>
    <automated>test -f "docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md" && echo "DEV LOG EXISTS"</automated>
  </verify>
  <done>Dev log exists with per-item evidence for all 10 Phase 2 contract items, each with a PASS/FAIL/NOT_IMPLEMENTED/N-A status backed by specific command output or grep evidence</done>
</task>

<task type="auto">
  <name>Task 2: Write closeout artifact and conditionally update roadmap</name>
  <files>docs/features/FEATURE-ris-phase2-closeout.md, docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md</files>
  <action>
Using the evidence collected in Task 1, create the closeout artifact at
`docs/features/FEATURE-ris-phase2-closeout.md` with this structure:

```markdown
# RIS Phase 2 Closeout

**Date:** 2026-04-09
**Spec:** SPEC-ris-phase2-operational-contracts.md
**Roadmap:** RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md

## Scope Completed

[One paragraph summary of what Phase 2 delivered]

## Acceptance Matrix

| # | Contract Item | Status | Evidence | Notes |
|---|---------------|--------|----------|-------|
| 1 | Fail-closed evaluation | PASS/FAIL | [test file + dev log ref] | |
| 2 | Weighted composite gate | ... | ... | |
[all 10 items]

## Commands Verified

[Bulleted list of exact CLI commands that were run and their result]

## Artifact Paths

[Bulleted list of key implementation artifacts with full repo paths]
- config/ris_eval_config.json
- packages/research/evaluation/config.py
- packages/research/evaluation/providers.py (Gemini + DeepSeek clients)
- packages/research/ingestion/review_integration.py
- tools/cli/research_review.py
- docs/eval/ris_retrieval_benchmark.jsonl
[etc]

## Test Evidence

[Exact test file names and pass counts from the focused suite run]

## Manual Validations Already Performed

[Reference the 6 dev logs from 2026-04-08 that document manual CLI smoke tests]

## Remaining Caveats / Deferred Items

[List items that are NOT IMPLEMENTED or have caveats -- be specific]
- Item 5 (budget caps): [status based on evidence]
- Item 9 (ClickHouse idempotency): [status -- Operator Guide says no RIS data in CH]
- Item 10 (posture statement): [status based on grep]
- rejection_audit_disagreement health check: deferred stub (Phase 3)
- 72-hour auto-promote/auto-reject policy: [status]
- Cloud provider live integration: implemented but requires API keys + RIS_ENABLE_CLOUD_PROVIDERS=1

## Recommendation

[One of:]
- **READY TO CLOSE** -- All 10 contract items pass (or are documented N/A with rationale).
  Mark Phase 2 complete in roadmap.
- **NOT READY** -- The following items block closure: [list specific blockers].
  Do not mark Phase 2 complete until these are addressed.
- **CONDITIONAL CLOSE** -- Core contract items (1-4, 6-8) pass. Items [X, Y] are
  not applicable to current architecture (document rationale). Items [Z] have known
  caveats that are acceptable for Phase 2 scope.
```

**Roadmap update rules:**
- Read `docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md`
- For each contract item with PASS status, change `- [ ]` to `- [x]` on the
  corresponding line
- For items with NOT_IMPLEMENTED or FAIL, leave as `- [ ]`
- For items that are genuinely N/A to the current architecture, change to
  `- [x]` with a note: `(N/A -- [rationale])`
- Update the `**Status:**` line at the top only if ALL items are checked:
  change `Pending Implementation` to `Complete (2026-04-09)` OR leave as-is
  if blockers remain
- Do NOT rewrite other content in the roadmap -- minimal edits only
- Do NOT update `**Last updated:**` date (this is not a content change, just status)

**If NOT READY:** Do not change the roadmap status line. Still check off individual
items that did pass. Write the closeout doc with the NOT READY recommendation and
list exact blockers.
  </action>
  <verify>
    <automated>test -f "docs/features/FEATURE-ris-phase2-closeout.md" && grep -c "Contract Item" "docs/features/FEATURE-ris-phase2-closeout.md"</automated>
  </verify>
  <done>Closeout artifact exists with acceptance matrix covering all 10 items. Roadmap checkboxes updated for passing items only. Recommendation is explicit and evidence-backed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries crossed -- this plan is read-only verification and documentation.
No code changes, no external API calls, no secrets handled.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-jfm-01 | I (Info Disclosure) | CLI output in dev log | accept | CLI commands run locally; no secrets in output. research-health/stats do not emit credentials. |
| T-jfm-02 | T (Tampering) | Roadmap checkbox edits | mitigate | Only change checkboxes for items with explicit test/grep evidence. Do not force-close items without evidence. |
</threat_model>

<verification>
- docs/features/FEATURE-ris-phase2-closeout.md exists with all 10 contract items addressed
- docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md exists with command output
- Roadmap checkboxes reflect actual evidence (items without evidence remain unchecked)
- No code files were modified
</verification>

<success_criteria>
- Closeout artifact has an acceptance matrix with PASS/FAIL/N-A for all 10 Phase 2 items
- Each disposition is backed by specific evidence (test output, grep result, or dev log ref)
- Remaining caveats are explicitly listed, not hidden
- Recommendation is one of: READY TO CLOSE / NOT READY / CONDITIONAL CLOSE
- Dev log records exact commands and output
- Roadmap edits are minimal and evidence-backed
</success_criteria>

<output>
After completion, create `.planning/quick/260409-jfm-phase-2-ris-acceptance-sweep-and-closeou/260409-jfm-SUMMARY.md`
</output>
