---
phase: quick-260403-jyl
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
  - docs/features/FEATURE-ris-dev-agent-integration-v1.md
  - tests/test_ris_integration_workflow.py
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md
autonomous: true
requirements: [RIS_07-dev-agent, RIS_07-fast-research]
must_haves:
  truths:
    - "CLAUDE.md contains a Research Intelligence System section with truthful CLI commands"
    - "Dev agent can find precheck/query/ingest instructions without reading spec files"
    - "Operator can preserve a fast-research URL finding into RIS using documented commands"
    - "Operator can preserve a manual summary into RIS using documented commands"
    - "Round-trip test proves precheck -> ingest -> query retrieves the ingested content"
    - "RIS_07 is marked closed at v1 scope in CURRENT_STATE.md"
  artifacts:
    - path: "CLAUDE.md"
      provides: "RIS section with precheck/query/ingest/acquire command reference"
      contains: "Research Intelligence System"
    - path: "docs/features/FEATURE-ris-dev-agent-integration-v1.md"
      provides: "Dev-agent workflow and fast-research preservation loop documentation"
      contains: "Dev Agent Integration"
    - path: "tests/test_ris_integration_workflow.py"
      provides: "Integration tests for precheck -> ingest -> query round-trip"
      min_lines: 50
    - path: "docs/CURRENT_STATE.md"
      provides: "RIS_07 closure entry"
      contains: "RIS_07"
    - path: "docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md"
      provides: "Dev log for this work"
  key_links:
    - from: "CLAUDE.md"
      to: "tools/cli/research_precheck.py"
      via: "documented command examples"
      pattern: "research-precheck run"
    - from: "CLAUDE.md"
      to: "tools/cli/research_ingest.py"
      via: "documented command examples"
      pattern: "research-ingest"
    - from: "CLAUDE.md"
      to: "tools/cli/research_acquire.py"
      via: "documented command examples"
      pattern: "research-acquire"
---

<objective>
Complete the dev-agent integration and fast-research preservation side of RIS_07.
Close RIS as a truthful end-to-end system.

Purpose: Dev agents (Claude Code, Codex, Gemini CLI) currently have no in-repo guidance
about the Research Intelligence System. CLAUDE.md lacks any RIS section. Operators have
no documented workflow for preserving fast-research findings (from LLM sessions, web
searches) into RIS. This plan adds the missing agent instructions, operator workflow
documentation, integration tests, and closes RIS_07 at v1 scope.

Output: Updated CLAUDE.md with RIS section, feature doc, integration tests, dev log,
CURRENT_STATE entry.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docs/reference/RAGfiles/RIS_07_INTEGRATION.md
@docs/CURRENT_STATE.md
@docs/dev_logs/2026-04-03_ris_r4_cli_truth_alignment.md

<interfaces>
<!-- Existing RIS CLI surface the plan documents (verified via --help) -->

research-precheck run --idea "description"
  -> Returns GO/CAUTION/STOP recommendation with supporting evidence

research-precheck inspect --idea "description"
  -> Shows enriched KnowledgeStore query output with provenance and contradictions

research-ingest --text "body" --title "title" --source-type manual --no-eval
  -> Ingests inline text into KS; --no-eval skips LLM scoring (manual trust)

research-ingest --file path/to/doc.md [--source-type TYPE] [--extract-claims]
  -> Ingests file into KS with optional claim extraction

research-acquire --url URL --source-family FAMILY [--no-eval] [--extract-claims]
  -> Fetches URL, normalizes, caches, ingests into KS
  -> source-family: academic, github, blog, news, book, reddit, youtube

research-acquire --search "query" --source-family academic [--max-results N]
  -> ArXiv topic search + batch ingest

rag-query --question "topic" --hybrid --rerank [--knowledge-store PATH]
  -> Queries the RAG index (includes KS if populated)
  -> --evidence-mode for structured claim output

research-report save --title "..." --body "..." [--tags TAG,TAG]
  -> Saves a research report to the catalog

research-report search --query "keyword"
  -> Searches past reports by keyword

research-stats summary [--json]
  -> Pipeline health snapshot

research-health
  -> Print health status from stored run data
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add RIS dev-agent section to CLAUDE.md and create integration feature doc</name>
  <files>CLAUDE.md, docs/features/FEATURE-ris-dev-agent-integration-v1.md</files>
  <action>
1. Read the current CLAUDE.md in full.

2. Add a new section "## Research Intelligence System (RIS)" AFTER the "### Research / dossier workflows" subsection and BEFORE the "### Planned but not yet implemented" subsection. The section must contain:

   a. **Purpose** (2 sentences): RIS is the project's persistent knowledge base. Before implementing a new strategy or feature, check what existing research says.

   b. **Dev Agent Pre-Build Workflow** (numbered steps):
      - Step 1: Run `python -m polytool research-precheck run --idea "description of planned work"`
      - Step 2: If STOP, do not proceed without operator discussion. If CAUTION, note the concerns. If GO, proceed.
      - Step 3: For deeper context, run `python -m polytool rag-query --question "relevant topic" --hybrid --rerank`
      - Step 4: If precheck cites contradictions, run `python -m polytool research-precheck inspect --idea "description"` for full provenance.

   c. **Preserving Findings into RIS** (for operator/agent use after a productive research session):
      - Save a URL: `python -m polytool research-acquire --url URL --source-family FAMILY --no-eval`
        (FAMILY = academic, github, blog, news, book, reddit, youtube)
      - Save a manual summary: `python -m polytool research-ingest --text "finding text" --title "Finding Title" --source-type manual --no-eval`
      - Save from file: `python -m polytool research-ingest --file path/to/notes.md --source-type manual --no-eval`

   d. **Pipeline health** (one-liner): `python -m polytool research-health` for status, `python -m polytool research-stats summary` for metrics.

   e. Note: "All RIS commands are offline-first and do not call external LLM APIs unless --provider ollama is used."

3. Also update the "### Research / dossier workflows" command list to add the missing RIS commands:
   - `research-precheck`
   - `research-ingest`
   - `research-acquire`
   - `research-report`
   - `research-health`
   - `research-stats`
   - `research-scheduler`

4. Create docs/features/FEATURE-ris-dev-agent-integration-v1.md with:
   - Title: "RIS Dev Agent Integration v1"
   - Status: Shipped (2026-04-03)
   - Sections: Purpose, Dev Agent Workflow, Fast-Research Preservation Loop, Operator Recipes, v2 Deferred Items
   - Operator Recipes: concrete copy-paste command sequences for the three main scenarios:
     (a) "I found a useful paper" -> research-acquire --url ... --source-family academic
     (b) "I learned something from a ChatGPT/Gemini session" -> research-ingest --text "..." --title "..."
     (c) "I want to check if RIS knows about X before building" -> research-precheck run --idea "..."
   - v2 Deferred Items:
     - Dossier-to-external-knowledge extraction (RIS_07 Section 1)
     - SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3)
     - ChatGPT architect integration via Google Drive (RIS_07 Section 4)
     - Auto-discovery -> knowledge loop (RIS_07 Section 2)
     - MCP polymarket_rag_query auto-routing (currently requires explicit rag-query CLI)

IMPORTANT: Every command example must match the SHIPPED CLI surface. Do NOT use `polytool research precheck` (subcommand syntax) -- the shipped commands use hyphenated names like `research-precheck`. Always prefix with `python -m polytool`.
  </action>
  <verify>
    <automated>grep -c "Research Intelligence System" CLAUDE.md && grep -c "research-precheck run" CLAUDE.md && test -f docs/features/FEATURE-ris-dev-agent-integration-v1.md && grep -c "research-acquire" docs/features/FEATURE-ris-dev-agent-integration-v1.md</automated>
  </verify>
  <done>
    - CLAUDE.md contains a "Research Intelligence System (RIS)" section with truthful command examples
    - All command examples use `python -m polytool research-*` format matching shipped CLI
    - FEATURE doc exists with operator recipes and deferred v2 items
    - No stale or invented command references
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Integration round-trip tests, CURRENT_STATE entry, and dev log</name>
  <files>tests/test_ris_integration_workflow.py, docs/CURRENT_STATE.md, docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md</files>
  <behavior>
    - Test 1 (precheck_round_trip): Ingest a doc via research-ingest --text, then run research-precheck run --idea on a related topic. Verify precheck returns exit 0 and output mentions the ingested content or returns a GO/CAUTION/STOP verdict.
    - Test 2 (ingest_text_then_query): Ingest a doc via research-ingest --text --title --no-eval, then query via rag-query --question matching the title. Verify the query returns the ingested document in results.
    - Test 3 (acquire_dry_run): Run research-acquire --url https://example.com --source-family blog --dry-run. Verify exit 0 and no files written to knowledge store (dry-run is safe offline).
    - Test 4 (ingest_file_round_trip): Write a temp .md file, ingest via research-ingest --file, query back via rag-query. Verify retrieval.
    - Test 5 (precheck_stop_on_contradiction): Ingest two contradicting documents, run precheck on a topic covered by both. Verify precheck output references contradiction or returns a non-GO verdict. (Best-effort -- depends on scoring; if not deterministic, verify the precheck at least returns exit 0 and produces output.)
  </behavior>
  <action>
1. Create tests/test_ris_integration_workflow.py with:
   - All tests use tmp_path for isolated KS (--db and --knowledge-store flags pointing to temp dirs)
   - Import main() from tools.cli.research_ingest, tools.cli.research_precheck, tools.cli.rag_query, tools.cli.research_acquire
   - Use capsys or StringIO to capture stdout
   - No network calls: use --no-eval on ingest, --dry-run on acquire
   - Follow the test patterns from existing test_ris_precheck.py and test_ris_research_acquire_cli.py

2. Implement the 5 tests described in the behavior block. Each test:
   - Sets up an isolated knowledge store in tmp_path
   - Calls CLI main() functions directly with argv lists
   - Asserts exit code 0 and meaningful output

3. Run the tests: `python -m pytest tests/test_ris_integration_workflow.py -x -v --tb=short`

4. Run full regression: `python -m pytest tests/ -x -q --tb=short`

5. Append a new section to docs/CURRENT_STATE.md (at the end, before any trailing blank lines):

```
## RIS_07 Dev Agent Integration and Fast-Research Preservation (quick-260403-jyl, 2026-04-03)

RIS_07 integration layer closed at practical v1 scope. CLAUDE.md now contains a
Research Intelligence System section with dev-agent pre-build workflow (precheck ->
query -> build) and fast-research preservation recipes (research-acquire for URLs,
research-ingest --text for manual findings).

**New/updated files:**
- `CLAUDE.md` -- RIS section added with truthful CLI command references
- `docs/features/FEATURE-ris-dev-agent-integration-v1.md` -- operator recipes, v2 deferred items

**Integration tests:** N new tests in `tests/test_ris_integration_workflow.py`
covering precheck round-trip, ingest-then-query, acquire dry-run, file ingest,
and contradiction detection.

**v2 deferred items (explicitly out of scope):**
- Dossier-to-external-knowledge extraction (RIS_07 Section 1)
- SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3)
- Auto-discovery -> knowledge loop (RIS_07 Section 2)
- MCP auto-routing for rag-query
```

Replace N with actual test count from the test run.

6. Create docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md with standard dev log format:
   - Date, task ID (quick-260403-jyl), objective
   - Files modified table
   - What was done (3 bullets: CLAUDE.md update, feature doc, integration tests)
   - Deferred items (v2 list matching CURRENT_STATE)
   - Commands run with results
   - Codex review tier: Skip (docs + tests only)
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_integration_workflow.py -x -v --tb=short</automated>
  </verify>
  <done>
    - All integration tests pass (5 tests, exit 0)
    - Full regression passes with no new failures
    - CURRENT_STATE.md has RIS_07 closure entry with v2 deferred items
    - Dev log exists at docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md
  </done>
</task>

</tasks>

<verification>
1. `grep "Research Intelligence System" CLAUDE.md` returns at least one match
2. `grep "research-precheck run" CLAUDE.md` returns at least one match (truthful command)
3. `grep -c "polytool research " CLAUDE.md` returns 0 (no stale subcommand-style references)
4. `python -m pytest tests/test_ris_integration_workflow.py -x -v --tb=short` -- all pass
5. `python -m pytest tests/ -x -q --tb=short` -- no regressions
6. `python -m polytool --help` still loads cleanly
7. `test -f docs/features/FEATURE-ris-dev-agent-integration-v1.md`
8. `grep "RIS_07" docs/CURRENT_STATE.md` returns at least one match
</verification>

<success_criteria>
- CLAUDE.md contains RIS section that any dev agent can follow to precheck ideas and preserve findings
- Every command reference in CLAUDE.md and FEATURE doc matches shipped CLI (no stale references)
- Integration tests prove the documented round-trip workflow actually works
- RIS_07 is closed in CURRENT_STATE.md with v2 items explicitly deferred
- Full test suite passes with no regressions
</success_criteria>

<output>
After completion, create `.planning/quick/260403-jyl-complete-the-dev-agent-integration-and-f/260403-jyl-SUMMARY.md`
</output>
