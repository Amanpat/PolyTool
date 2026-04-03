---
phase: quick-260403-lix
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/reference/RAGfiles/RIS_07_INTEGRATION.md
  - docs/reference/RAGfiles/RIS_OVERVIEW.md
  - docs/features/FEATURE-ris-synthesis-engine-v1.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md
autonomous: true
requirements: [RIS-TRUTH-01]

must_haves:
  truths:
    - "FEATURE-ris-synthesis-engine-v1.md no longer claims precheck/report CLIs are absent"
    - "RIS_07_INTEGRATION.md uses shipped command forms (research-acquire, research-ingest, research-precheck run, rag-query) not stale polytool research subcommand forms"
    - "RIS_07_INTEGRATION.md ChatGPT architect / Google Drive paragraph is labeled [v2 deferred]"
    - "RIS_OVERVIEW.md Infrastructure row reflects actual shipped CLI prefix pattern"
    - "CURRENT_STATE.md RIS_07 section notes dossier extraction shipped at v1 scope, auto-trigger deferred"
    - "CURRENT_STATE.md has a final RIS v1 COMPLETE closure statement"
    - "Dev log created with all changes, commands run, and final v1 vs v2 split"
  artifacts:
    - path: docs/reference/RAGfiles/RIS_07_INTEGRATION.md
      provides: Corrected command forms and deferred labels
    - path: docs/reference/RAGfiles/RIS_OVERVIEW.md
      provides: Corrected CLI row in Infrastructure table
    - path: docs/features/FEATURE-ris-synthesis-engine-v1.md
      provides: Corrected deferred section (CLI wiring now shipped)
    - path: docs/CURRENT_STATE.md
      provides: Corrected RIS_07 dossier paragraph + final RIS v1 COMPLETE closure
    - path: docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md
      provides: Closure dev log
  key_links:
    - from: docs/features/FEATURE-ris-synthesis-engine-v1.md
      to: tools/cli/research_precheck.py + tools/cli/research_report.py
      via: "Deferred items section updated to reflect both CLIs now shipped"
    - from: docs/reference/RAGfiles/RIS_07_INTEGRATION.md
      to: CLAUDE.md
      via: "Command examples updated to match shipped research-acquire / research-ingest / research-precheck run forms per CLAUDE.md"
---

<objective>
Close final truth-alignment gaps across RIS v1 documentation so Codex can declare RIS v1 complete.

Purpose: Codex found truth drift between reference docs, feature docs, and shipped command surfaces. The goal is accurate v1 narrative — not rewriting history, not inventing capabilities.

Output: Five updated docs + one dev log. All RIS reference docs and CURRENT_STATE reflect the v1 command surface and deferred v2 items clearly.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/reference/RAGfiles/RIS_07_INTEGRATION.md
@D:/Coding Projects/Polymarket/PolyTool/docs/reference/RAGfiles/RIS_OVERVIEW.md
@D:/Coding Projects/Polymarket/PolyTool/docs/features/FEATURE-ris-synthesis-engine-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/features/FEATURE-ris-dev-agent-integration-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md

<interfaces>
<!-- Shipped CLI commands (from polytool/__main__.py registrations) -->
<!-- All of these are standalone hyphenated commands, not `polytool research X` subcommands -->

research-precheck     -> tools/cli/research_precheck.py
  shipped subcommands: run --idea "..." [--no-ledger], override, outcome, history, inspect
  backward compat: research-precheck --idea "..." (no subcommand)

research-report       -> tools/cli/research_report.py
  shipped subcommands: save --title "..." --body "...", list --window 7d, search --query "...", digest --window 7

research-acquire      -> tools/cli/research_acquire.py
  shipped flags: --url URL --source-family FAMILY --no-eval, --search QUERY --max-results N

research-ingest       -> tools/cli/research_ingest.py
  shipped flags: --text "...", --file PATH, --source-type TYPE, --no-eval, --title "..."

rag-query             -> tools/cli/rag_query.py (existing)
  shipped flags: --question "...", --hybrid, --knowledge-store default

research-health       -> tools/cli/research_health.py
research-stats        -> tools/cli/research_stats.py
research-scheduler    -> tools/cli/research_scheduler.py
research-dossier-extract -> tools/cli/research_dossier_extract.py
  shipped flags: --dossier-dir PATH, --batch

<!-- v1 SHIPPED summary (from CURRENT_STATE.md entries) -->
R0: Knowledge store foundation (quick-055)
R1: Academic ingestion (quick-260402-wj3)
R2: Social ingestion (quick-260402-wj9)
R3: Synthesis engine -- deterministic (quick-260402-xbo)
R4: Infrastructure -- scheduler, health, stats, report catalog (quick-260403-1s3, 1sc, 1sg, xbt)
R5: Dossier pipeline + discovery loop (quick-260403-jy8)
Dev agent integration: CLAUDE.md + feature doc (quick-260403-jyl)
SimTrader bridge: brief_to_candidate, precheck_to_candidate, register_research_hypothesis (quick-260403-jyg)

<!-- v2 DEFERRED items (from FEATURE-ris-dev-agent-integration-v1.md) -->
- Auto-trigger dossier extraction after wallet-scan (hook not wired)
- Auto-discovery -> knowledge loop (requires auto-trigger as prerequisite)
- SimTrader auto-promotion loop (bridge shipped but auto-loop not wired)
- ChatGPT architect / Google Drive connector (requires manual drive sync)
- MCP polymarket_rag_query -> KnowledgeStore routing (MCP queries Chroma only)
- LLM-based synthesis / DeepSeek V3 synthesis
- n8n migration
- ClickHouse ingestion_log table + Grafana panels
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix RIS_07_INTEGRATION.md and RIS_OVERVIEW.md command-surface truth drift</name>
  <files>
    docs/reference/RAGfiles/RIS_07_INTEGRATION.md
    docs/reference/RAGfiles/RIS_OVERVIEW.md
  </files>
  <action>
Read both files first, then make targeted edits. Do NOT rewrite prose unnecessarily.

**RIS_07_INTEGRATION.md — three patches:**

Patch A: Section 4 "Direct query via MCP" code block (line ~236).
Replace: `polytool research precheck --idea "Implement momentum signal for crypto pair bot"`
With: `python -m polytool research-precheck run --idea "Implement momentum signal for crypto pair bot" --no-ledger`

Patch B: Section 4 "CLAUDE.md integration" snippet (lines ~246-248).
Replace the two example commands:
```
## Research Intelligence System
Before implementing a new strategy or feature, check existing research:
- Run: polytool research precheck --idea "description"
- Query: polytool research query "relevant topic"
```
With:
```
## Research Intelligence System
Before implementing a new strategy or feature, check existing research:
- Run: python -m polytool research-precheck run --idea "description" --no-ledger
- Query: python -m polytool rag-query --question "relevant topic" --hybrid --knowledge-store default
```

Patch C: Section 4 "How the ChatGPT architect uses the RIS" paragraph (lines ~251-256).
Prepend a `**[v2 deferred — requires manual Google Drive sync setup]**` note immediately before the paragraph text. Do not delete the paragraph — just label it deferred. Example:

> **[v2 deferred — requires manual Google Drive sync setup]**
> 
> The ChatGPT architect (Google Drive connector) can access research reports...

Patch D: Section 5 "Bridge: Fast research -> RIS" (lines ~280-284).
The two command examples use non-existent `polytool research ingest-url` and `polytool research ingest-manual`. Replace:
```
2. `polytool research ingest-url "source_url"` captures the source permanently
3. Or manually writes a summary: `polytool research ingest-manual --title "..." --text "..."`
```
With:
```
2. `python -m polytool research-acquire --url "source_url" --source-family blog --no-eval` captures the source permanently
3. Or manually writes a summary: `python -m polytool research-ingest --text "..." --title "..." --source-type manual --no-eval`
```

**RIS_OVERVIEW.md — one patch:**

The Infrastructure table row reads:
`CLI: polytool research {ingest,query,report,precheck,stats}`

Replace with:
`CLI: python -m polytool research-{ingest,acquire,report,precheck,stats,health,scheduler,dossier-extract} (standalone hyphenated commands)`

Also update the Integration row to note dossier pipeline is v1 shipped:
Current: `Dossier pipeline upgrade · SimTrader bridge (v2)`
Replace with: `Dossier pipeline upgrade (v1 shipped) · SimTrader bridge (v1 shipped, auto-loop v2)`
  </action>
  <verify>
Read both updated files and confirm:
- `polytool research ingest-url` does NOT appear in RIS_07_INTEGRATION.md
- `polytool research precheck` (without `python -m`) does NOT appear outside the CLAUDE.md snippet context
- ChatGPT architect paragraph has `[v2 deferred` label
- RIS_OVERVIEW.md Infrastructure CLI row uses `python -m polytool research-*` format
  </verify>
  <done>All four patches applied; stale `polytool research X` command forms replaced with shipped `python -m polytool research-*` equivalents; ChatGPT architect section labeled deferred; dossier status updated in overview table.</done>
</task>

<task type="auto">
  <name>Task 2: Fix FEATURE-ris-synthesis-engine-v1.md and CURRENT_STATE.md truth drift, write dev log</name>
  <files>
    docs/features/FEATURE-ris-synthesis-engine-v1.md
    docs/CURRENT_STATE.md
    docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md
  </files>
  <action>
Read all three files first, then make targeted edits.

**FEATURE-ris-synthesis-engine-v1.md — one patch:**

The "What Is NOT Built (Deferred)" section contains:
```
- **CLI commands for report generation** -- `polytool research report --topic ...` and
  `polytool research precheck --idea ...` are not yet wired to CLI.
- **Report storage/catalog** -- Reports are not saved to `artifacts/research/reports/`.
```

These are now SHIPPED. Replace those two bullet points with:

```
- **CLI commands for report generation** -- `python -m polytool research-report` (save/list/search/digest) and `python -m polytool research-precheck` (run/override/outcome/history/inspect) are **shipped** as of quick-260402-xbt and quick-260401-o1q respectively. The precheck CLI wraps the deterministic `synthesize_precheck()` output.
- **Report storage/catalog** -- `research-report save/list/search` shipped as of quick-260402-xbt. Reports saved to SQLite index + markdown files under `artifacts/research/reports/`.
```

The other deferred items in that section (LLM-based synthesis, weekly digest, ClickHouse report indexing, past failures search, HyDE integration) remain deferred — do NOT remove them.

**CURRENT_STATE.md — two patches:**

Patch A: The RIS_07 dev-agent section (around line 1282-1285) lists v2 deferred items including:
`- Dossier-to-external-knowledge extraction (RIS_07 Section 1)`

This is now SHIPPED at v1 scope (quick-260403-jy8). Update that bullet to:
`- Dossier-to-external-knowledge extraction (RIS_07 Section 1): **v1 shipped** — CLI + batch extract via research-dossier-extract. Auto-trigger after wallet-scan remains v2 deferred.`

Also remove the line:
`- SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3)`
from the deferred list (it was shipped as quick-260403-jyg — brief_to_candidate, register_research_hypothesis exist; the auto-loop is deferred but the bridge itself shipped). Replace it with:
`- SimTrader auto-promotion loop (RIS_07 Section 3): bridge functions shipped (quick-260403-jyg), auto-hypothesis generation loop v2 deferred.`

Patch B: After the last RIS entry (quick-260403-jy8 block, around line 1321), append a new closure section:

```markdown
## RIS v1 — Complete (2026-04-03)

All practical v1 scope RIS subsystems are shipped and passing 3660 tests.

**v1 Complete:**
- R0: Knowledge store foundation (SQLite + Chroma, BGE-M3 embeddings)
- R1: Academic ingestion (ArXiv search, BookAdapter, manual URL, --extract-claims)
- R2: Social ingestion (Reddit, YouTube, clean_transcript)
- R3: Synthesis engine (deterministic ReportSynthesizer, EnhancedPrecheck, ResearchBrief)
- R4: Infrastructure (scheduler 8-job, health checks 6-condition, stats/metrics export, report catalog save/list/search/digest)
- R5: Dossier pipeline (DossierExtractor, DossierAdapter, research-dossier-extract CLI, batch mode)
- Dev agent integration (CLAUDE.md RIS section, operator recipes A-E, 10 integration tests)
- SimTrader bridge (brief_to_candidate, precheck_to_candidate, register_research_hypothesis, record_validation_outcome)

**v2 Deferred (require Phase 3+ or additional infra):**
- Auto-trigger dossier extraction after wallet-scan (hook not wired)
- Auto-discovery -> knowledge loop (requires auto-trigger prerequisite)
- SimTrader auto-promotion loop (bridge shipped; auto-loop not wired)
- LLM-based synthesis (DeepSeek V3 prose generation)
- n8n migration from APScheduler
- ClickHouse ingestion_log table + Grafana panels
- ChatGPT architect / Google Drive connector
- MCP rag-query -> KnowledgeStore routing
- Weekly digest automation
- SSRN ingestion, Twitter/X ingestion

All 3660 tests pass. Codex review: docs-only changes, skip tier.
```

**Dev log: docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md**

Create new dev log with:
- Date: 2026-04-03, Plan: quick-260403-lix
- Objective: truth alignment (not feature work)
- Files changed table with each file and the specific mismatches corrected
- Commands run section with smoke test results
- Final v1 complete vs v2 deferred statement
- Codex review: docs-only, skip tier

Smoke test commands to run after edits and record output in the dev log:
```
python -m polytool research-precheck run --idea "test" --no-ledger 2>&1 | head -5
python -m polytool research-report list --window 1d 2>&1 | head -5
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -3
```

Record exact output lines in the dev log.
  </action>
  <verify>
Check all three conditions:
1. FEATURE doc "not yet wired to CLI" phrase is gone; replaced with "shipped" note
2. CURRENT_STATE.md has "RIS v1 — Complete" section after line 1321
3. Dev log exists at docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md with test pass count
  </verify>
  <done>
- FEATURE-ris-synthesis-engine-v1.md: precheck and report-catalog deferred bullets updated to shipped
- CURRENT_STATE.md: RIS_07 dossier deferred item corrected; SimTrader bridge bullet corrected; RIS v1 COMPLETE closure section appended
- Dev log created with all mismatches, commands, and final v1/v2 split
- All tests still pass (no code changes)
  </done>
</task>

</tasks>

<verification>
- `python -m polytool --help` loads without import errors
- `python -m pytest tests/ -x -q --tb=short` passes with 3660 tests (no regressions — no code was changed)
- `grep -r "ingest-url\|ingest-manual\|polytool research precheck --idea\|polytool research query" docs/reference/RAGfiles/` returns no matches (stale command forms removed)
- `grep "not yet wired to CLI" docs/features/FEATURE-ris-synthesis-engine-v1.md` returns no matches
- `grep "RIS v1 — Complete" docs/CURRENT_STATE.md` returns a match
</verification>

<success_criteria>
Five files updated with targeted truth-alignment patches. Zero code changes. All 3660 tests continue passing. Dev log created. Codex can review the docs and call RIS v1 complete because:
1. No doc claims an absent CLI that is actually present
2. No doc uses a command form (`polytool research X`) that does not match the shipped hyphenated form (`python -m polytool research-X`)
3. Deferred v2 items are clearly labeled as deferred (not missing)
4. CURRENT_STATE.md has an explicit RIS v1 COMPLETE closure entry
</success_criteria>

<output>
After completion, create `.planning/quick/260403-lix-close-final-truth-alignment-gaps-for-ris/260403-lix-SUMMARY.md`
</output>
