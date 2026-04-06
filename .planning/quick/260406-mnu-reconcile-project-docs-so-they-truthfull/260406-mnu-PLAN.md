---
phase: quick-260406-mnu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
  - docs/PLAN_OF_RECORD.md
  - docs/ARCHITECTURE.md
  - docs/CURRENT_STATE.md
  - README.md
  - docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
  - docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "No doc in the repo falsely claims n8n is absent or Phase-3-only without acknowledging the shipped RIS pilot"
    - "No doc overstates n8n maturity -- pilot/scoped/opt-in language is preserved everywhere"
    - "APScheduler remains documented as the default/fallback scheduler"
    - "README no longer directs users to the dead simtrader branch"
  artifacts:
    - path: "CLAUDE.md"
      provides: "Corrected n8n scheduling language"
      contains: "RIS n8n pilot"
    - path: "docs/ARCHITECTURE.md"
      provides: "Control-plane row acknowledges RIS pilot"
      contains: "RIS n8n pilot"
    - path: "docs/CURRENT_STATE.md"
      provides: "Roadmap-not-implemented section qualified"
      contains: "scoped RIS n8n pilot"
    - path: "docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md"
      provides: "Dev log of all contradictions found and resolved"
  key_links:
    - from: "CLAUDE.md"
      to: "docs/adr/0013-ris-n8n-pilot-scoped.md"
      via: "ADR reference in scheduling language"
      pattern: "ADR.0013"
---

<objective>
Reconcile project docs so they truthfully describe the current RIS n8n pilot state.

Purpose: Multiple high-authority docs (CLAUDE.md, ARCHITECTURE.md, CURRENT_STATE.md, PLAN_OF_RECORD.md) contain blanket statements like "no n8n orchestration until Phase 3" that are now false -- the RIS n8n pilot (ADR 0013) is shipped, runtime-verified, and running n8n 2.14.2. These stale statements will mislead future Claude sessions and human operators. The README also still directs users to the dead `simtrader` branch.

Output: All listed docs updated with precise language. One dev log documenting every contradiction found and the final truth statement adopted.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docs/PLAN_OF_RECORD.md
@docs/ARCHITECTURE.md
@docs/CURRENT_STATE.md
@README.md
@docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
@docs/adr/0013-ris-n8n-pilot-scoped.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md
@docs/dev_logs/2026-04-05_ris_n8n_final_truth_reconcile.md
@docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix all n8n contradiction statements across 6 docs</name>
  <files>
    CLAUDE.md,
    docs/PLAN_OF_RECORD.md,
    docs/ARCHITECTURE.md,
    docs/CURRENT_STATE.md,
    README.md,
    docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
  </files>
  <action>
Apply the following EXACT edits. The truth statement for all edits is: "A scoped RIS n8n pilot (ADR 0013) is shipped and runtime-verified on n8n 2.14.2. It covers RIS ingestion workflows only. APScheduler remains the default/fallback scheduler for all non-RIS scheduling. The broad Phase 3 n8n control plane (full orchestration, approval flows, strategy automation) is NOT shipped."

**CLAUDE.md** (2 edits):

1. Line 41 -- replace:
   `- No n8n orchestration until Phase 3.`
   with:
   `- Broad n8n orchestration is deferred to Phase 3, but a scoped RIS n8n pilot (ADR 0013) is shipped and opt-in via `--profile ris-n8n`.`

2. Line 119 -- replace:
   `- **Scheduling**: Phase 1 uses cron / APScheduler; Phase 3 may add n8n.`
   with:
   `- **Scheduling**: APScheduler is the default scheduler. A scoped n8n pilot handles RIS ingestion workflows (opt-in via `--profile ris-n8n`, see ADR 0013). Broad n8n orchestration remains a Phase 3 target.`

**docs/ARCHITECTURE.md** (1 edit):

1. Line 15 -- the "Control plane" row's "Current architecture truth" cell. Replace:
   `The repo is still CLI-first and local-first. \`services/api/\` exists, but the broad v4 wrapper surface and n8n control plane are not current architecture truth.`
   with:
   `The repo is CLI-first and local-first. A scoped RIS n8n pilot (ADR 0013, n8n 2.14.2) handles RIS ingestion workflows via \`--profile ris-n8n\`. The broad v4 wrapper surface and full n8n control plane are not current architecture truth.`

**docs/PLAN_OF_RECORD.md** (1 edit):

1. Line 18 -- the "Automation / hosting" row's "Current implementation-policy truth" cell. Replace:
   `Current operating policy stays local-first. AWS is not required by any shipped milestone, and the broader automation stack is not current-state truth yet.`
   with:
   `Current operating policy stays local-first. A scoped RIS n8n pilot (ADR 0013) is shipped for RIS ingestion workflows only. The broader automation stack (full n8n control plane, Discord ops, AWS) is not current-state truth. AWS is not required by any shipped milestone.`

**docs/CURRENT_STATE.md** (1 edit):

1. Near line 18 -- replace:
   `- The v4 control plane is not shipped: no n8n orchestration layer, no broad FastAPI wrapper surface, no Discord approval system, and no automated feedback loop.`
   with:
   `- The v4 control plane is not shipped: no broad n8n orchestration layer, no broad FastAPI wrapper surface, no Discord approval system, and no automated feedback loop. (A scoped RIS n8n pilot exists for RIS ingestion workflows only -- see ADR 0013 and the RIS n8n sections below.)`

**README.md** (1 edit):

1. Lines 71-78 -- replace the clone + checkout block:
   ```
   git clone https://github.com/Amanpat/PolyTool.git
   cd PolyTool
   git checkout simtrader
   ```
   and the paragraph `Why this branch: \`simtrader\` is the active development branch with the full execution layer. Do not use \`main\` -- it is behind.`
   with:
   ```
   git clone https://github.com/Amanpat/PolyTool.git
   cd PolyTool
   ```
   and the paragraph `The repo uses a single branch (\`main\`). All prior feature branches were consolidated into main as of 2026-04-06.`

**docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md** (1 footnote-style addition):

1. After line 679 (`n8n is deferred to Phase 3. Until then, APScheduler or cron handles scheduling.`), add a new line:
   `> **Note (2026-04-06):** A scoped RIS n8n pilot (ADR 0013) is already shipped for RIS ingestion workflows. This pilot is opt-in (\`--profile ris-n8n\`) and does not constitute the Phase 3 broad n8n orchestration described below. APScheduler remains the default scheduler.`

Do NOT touch any code files, .claude/*, infra/n8n workflow JSON, or docker-compose runtime behavior.
Do NOT rewrite roadmap strategy or phase structure.
Do NOT remove the Phase 3 n8n sections from the roadmap -- they describe the BROAD orchestration target which is still future work.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && echo "=== Stale phrases that should be GONE ===" && rtk grep -c "No n8n orchestration until Phase 3" CLAUDE.md && rtk grep -c "Phase 3 may add n8n" CLAUDE.md && rtk grep -c "git checkout simtrader" README.md && echo "=== Qualified phrases that SHOULD exist ===" && rtk grep -c "scoped RIS n8n pilot" CLAUDE.md docs/ARCHITECTURE.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md && rtk grep -c "ADR.0013" CLAUDE.md docs/ARCHITECTURE.md</automated>
  </verify>
  <done>
    - CLAUDE.md lines 41 and 119 no longer contain blanket "no n8n" / "Phase 3 may add n8n" statements
    - ARCHITECTURE.md control-plane row acknowledges the RIS pilot
    - PLAN_OF_RECORD.md automation row acknowledges the RIS pilot
    - CURRENT_STATE.md "not shipped" bullet is qualified with the RIS pilot exception
    - README.md no longer directs to the dead simtrader branch
    - Roadmap v5.1 has a footnote under the n8n Phase 3 section acknowledging the shipped pilot
    - Every updated statement preserves "scoped / opt-in / pilot" language -- nothing overstates maturity
    - APScheduler is still documented as default/fallback in every location
  </done>
</task>

<task type="auto">
  <name>Task 2: Create closeout dev log documenting contradictions and final truth</name>
  <files>docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md</files>
  <action>
Create `docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md` with:

**Header:**
```
# RIS n8n Truth Docs Closeout -- 2026-04-06

**Quick ID:** 260406-mnu
**Scope:** Docs-only. No code, config, workflow JSON, or docker-compose runtime changes.
```

**Section: Contradictions Found and Resolved**

Table with columns: File | Line(s) | Old Statement | Problem | New Statement

Rows:
1. CLAUDE.md | 41 | "No n8n orchestration until Phase 3." | False -- RIS n8n pilot is shipped (ADR 0013, n8n 2.14.2) | Qualified: broad orchestration deferred, scoped pilot shipped
2. CLAUDE.md | 119 | "Phase 1 uses cron / APScheduler; Phase 3 may add n8n." | Stale -- n8n already handles RIS scheduling | APScheduler default + scoped n8n pilot for RIS
3. docs/ARCHITECTURE.md | 15 | Control plane row says no n8n truth | Omits RIS pilot | Row now mentions RIS n8n pilot (ADR 0013)
4. docs/PLAN_OF_RECORD.md | 18 | "broader automation stack is not current-state truth yet" | Omits that RIS n8n IS truth for RIS subsystem | Now acknowledges RIS pilot
5. docs/CURRENT_STATE.md | 18 | "no n8n orchestration layer" | Contradicted by sections at line 1487+ in same file | Qualified with "no broad" + parenthetical exception
6. README.md | 71-78 | "git checkout simtrader" / "Do not use main" | Branch is dead; repo is main-only since 2026-04-06 | Removed branch checkout; added main-only note
7. docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md | 679 | "n8n is deferred to Phase 3" with no exception | True for broad orchestration, but misleading without pilot footnote | Added blockquote footnote referencing ADR 0013

**Section: Final Truth Statement**

```
RIS n8n pilot (ADR 0013) status as of 2026-04-06:
- SHIPPED: 11 workflow templates, n8n 2.14.2, docker-beside-docker bridge pattern
- SCOPE: RIS ingestion workflows only (research-scheduler run-job, health, status, manual acquire)
- ACTIVATION: opt-in via --profile ris-n8n (never starts in default compose stack)
- DEFAULT SCHEDULER: APScheduler remains the default for all scheduling
- NOT SHIPPED: broad Phase 3 n8n control plane, Discord approval, strategy automation, full FastAPI wrapper
- OPERATOR GUIDE: docs/RIS_OPERATOR_GUIDE.md
- ADR: docs/adr/0013-ris-n8n-pilot-scoped.md
```

**Section: Files Changed**

List all 7 files from Task 1 plus this dev log.

**Section: Verification Commands Run**

Include the grep commands and their results showing stale phrases are gone and qualified phrases exist.

**Section: What Was NOT Changed**

- docs/adr/0013-ris-n8n-pilot-scoped.md (already correct per prior reconciliation passes)
- docs/RIS_OPERATOR_GUIDE.md (already reconciled in quick-260404-uav and quick-260405-g4j)
- .claude/* (out of scope per constraints)
- Code files, infra/n8n workflow JSON, docker-compose.yml (out of scope)
- Roadmap phase structure and strategy (preserved as-is; only a footnote added)

**Section: Codex Review**

Tier: Skip (docs-only, no execution/strategy/risk logic).
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md" && echo "Dev log exists"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md
    - Contains contradiction table with all 7 items
    - Contains final truth statement
    - Contains files-changed list and verification commands
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply. This is a docs-only change with no runtime, authentication, or data-handling impact.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Information Disclosure | docs/ | accept | All changes are to public docs already committed to the repo. No secrets or private data introduced. |
</threat_model>

<verification>
1. Run `git diff -- CLAUDE.md docs/PLAN_OF_RECORD.md docs/ARCHITECTURE.md docs/CURRENT_STATE.md README.md docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` and confirm changes are limited to the described edits.
2. Grep for stale phrases that should be eliminated or qualified:
   - `grep -r "No n8n orchestration until Phase 3" CLAUDE.md` -- expect 0 matches
   - `grep -r "Phase 3 may add n8n" CLAUDE.md` -- expect 0 matches
   - `grep -r "git checkout simtrader" README.md` -- expect 0 matches
3. Grep for new qualified phrases that should exist:
   - `grep -r "scoped RIS n8n pilot" CLAUDE.md docs/ARCHITECTURE.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md` -- expect 4+ matches
   - `grep -r "ADR 0013" CLAUDE.md docs/ARCHITECTURE.md` -- expect 2+ matches
4. Confirm `python -m polytool --help` still loads (no import side-effects from doc changes -- sanity check).
</verification>

<success_criteria>
- Zero blanket "no n8n" statements remain in CLAUDE.md, ARCHITECTURE.md, PLAN_OF_RECORD.md, or CURRENT_STATE.md
- Every n8n reference in updated docs uses "scoped", "pilot", "opt-in", or "RIS-only" qualifying language
- APScheduler documented as default/fallback in CLAUDE.md scheduling section
- README directs to main branch, not simtrader
- Roadmap v5.1 has pilot footnote without structural changes
- Dev log exists with full contradiction inventory
</success_criteria>

<output>
After completion, create `.planning/quick/260406-mnu-reconcile-project-docs-so-they-truthfull/260406-mnu-SUMMARY.md`
</output>
