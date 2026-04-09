---
phase: 260409-jfi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
  - docs/README.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md
autonomous: true
requirements: [docs-reconcile-phase2-ris]
must_haves:
  truths:
    - "README.md RIS CLI table includes research-review command"
    - "README.md RIS section accurately describes evaluation gate behavior (weighted composite, fail-closed, Gemini/DeepSeek/Ollama routing)"
    - "RIS_OPERATOR_GUIDE.md no longer claims cloud LLM providers are v2 deliverables or raise ValueError"
    - "RIS_OPERATOR_GUIDE.md documents research-review CLI (list/inspect/accept/reject/defer)"
    - "RIS_OPERATOR_GUIDE.md documents ACCEPT/REVIEW/REJECT/BLOCKED dispositions"
    - "RIS_OPERATOR_GUIDE.md documents retrieval benchmark command with query-class segmentation"
    - "RIS_OPERATOR_GUIDE.md documents overall_category in research-health output"
    - "CURRENT_STATE.md has entries for the 4 shipped Phase 2 work items"
    - "docs/README.md links to RIS_OPERATOR_GUIDE.md in workflows section"
    - "Dev log created documenting all changes"
  artifacts:
    - path: "README.md"
      provides: "Accurate RIS CLI reference and evaluation gate description"
    - path: "docs/RIS_OPERATOR_GUIDE.md"
      provides: "Truthful operator guide reflecting all Phase 2 shipped behavior"
    - path: "docs/CURRENT_STATE.md"
      provides: "Phase 2 shipped-truth entries"
    - path: "docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md"
      provides: "Mandatory dev log for this work"
  key_links: []
---

<objective>
Reconcile all active operator-facing docs so they accurately reflect shipped RIS Phase 2 behavior.

Purpose: Four Phase 2 code ships (cloud provider routing, ingest/review integration, monitoring truth, retrieval benchmark truth) have landed but the operator docs still contain stale v1-era claims. Operators following the guide will hit incorrect information about cloud providers ("v2 deliverables"), miss the review queue CLI entirely, and not know about segmented retrieval benchmarks or the new health overall_category output.

Output: Updated README.md, docs/README.md, docs/RIS_OPERATOR_GUIDE.md, docs/CURRENT_STATE.md, plus a mandatory dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@README.md
@docs/README.md
@docs/CURRENT_STATE.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/dev_logs/2026-04-08_ris_phase2_cloud_provider_routing.md
@docs/dev_logs/2026-04-08_ris_phase2_ingest_review_integration.md
@docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
@docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md
@docs/dev_logs/2026-04-08_ris_phase2_review_queue_cli.md
@docs/specs/SPEC-ris-phase2-operational-contracts.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix RIS_OPERATOR_GUIDE.md stale claims and add Phase 2 shipped behavior</name>
  <files>docs/RIS_OPERATOR_GUIDE.md</files>
  <action>
This is the highest-impact file. Apply these specific edits:

1. **"What Does NOT Work Yet [PLANNED]" section (line ~391-409):**
   - REMOVE the bullet "Cloud LLM evaluation providers -- Gemini, DeepSeek, OpenAI, Anthropic all raise ValueError when called. These are 'RIS v2 deliverables.'" This is now FALSE. Gemini and DeepSeek are implemented. Update to: Cloud providers for Gemini and DeepSeek are shipped (requires `RIS_ENABLE_CLOUD_PROVIDERS=1` plus API keys). OpenAI and Anthropic remain unimplemented.
   - Keep "LLM-based report synthesis" as still PLANNED (that is still v2).
   - Keep "Grafana panels", "ClickHouse tables", "Multi-hop query planning", "past_failures in precheck", "Auto-promotion", "rejection_audit_disagreement" as still PLANNED.

2. **Troubleshooting section (line ~425-426):**
   - REMOVE or rewrite the "Provider gemini is a RIS v2 deliverable" troubleshooting entry. Replace with: "Provider unavailable / timeout" -- If a cloud provider times out or is rate-limited, the evaluator routes to the next provider in the chain (gemini -> deepseek -> ollama). Check `research-health` for provider failure counts. Ensure `RIS_ENABLE_CLOUD_PROVIDERS=1` and the relevant API key env vars are set.

3. **Environment variables table (line ~452-459):**
   - REMOVE or update the `RIS_ENABLE_CLOUD_PROVIDERS` row from "No effect" to: "Set to `1` to enable Gemini/DeepSeek cloud routing for evaluation gate scoring."
   - ADD rows for: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), `DEEPSEEK_API_KEY`, and the `RIS_EVAL_*` override env vars from the cloud provider routing dev log.

4. **Add new section "Review Queue" after "Health Monitoring" section (~line 275):**
   Add a new section documenting the review queue CLI. Content:
   - Quick reference: `python -m polytool research-review list`, `research-review inspect <doc_id>`, `research-review accept <doc_id>`, `research-review reject <doc_id>`, `research-review defer <doc_id>`
   - Explain the 4 dispositions: ACCEPT (auto-ingests), REVIEW (queues to pending_review for operator action), REJECT (does not ingest), BLOCKED (scorer failure, also queues for visibility)
   - Mention `--db` flag for pointing at a specific knowledge store if not using the default path.
   - Note that `pending_review` has an append-only audit history (`pending_review_history`).

5. **Add new section "Evaluation Gate" near the top of "Advanced Workflows" or as a new section before "Health Monitoring":**
   Document the shipped weighted composite gate:
   - Formula: relevance*0.30 + novelty*0.25 + actionability*0.25 + credibility*0.20
   - Per-dimension floors: relevance >= 2, credibility >= 2 (waived for priority_1)
   - Provider routing: gemini -> deepseek -> ollama (configurable via `RIS_EVAL_PRIMARY_PROVIDER` etc.)
   - Fail-closed behavior: any provider error/timeout/parse failure = REJECT with `reject_reason="scorer_failure"`
   - Priority tier thresholds: priority_1 >= 2.5, priority_2 >= 3.0, priority_3 >= 3.2, priority_4 >= 3.5
   - Reference: `python -m polytool research-eval eval --title "..." --body "..." [--provider gemini] [--enable-cloud] [--json]`

6. **Add new section "Retrieval Benchmark" after "Claim Extraction" or near existing rag-eval references:**
   Document:
   - Command: `python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl`
   - Query classes: factual, analytical, exploratory
   - 8 required metrics (query_count, mean_recall_at_k, mean_mrr_at_k, total_scope_violations, queries_with_violations, mean_latency_ms, p50_latency_ms, p95_latency_ms)
   - Artifacts: `kb/rag/eval/reports/<timestamp>/report.json` and `summary.md` with per_class_modes, corpus_hash, eval_config
   - Hash verification: `python -m polytool rag-eval --suite ... --suite-hash-only`

7. **Update "last verified" date at top to 2026-04-09.**

Do NOT rewrite the entire file. Apply targeted edits to the specific sections listed above. Preserve all existing content that is still accurate (n8n sections, scheduler sections, file layout, etc.).
  </action>
  <verify>
    <automated>rtk grep -n "v2 deliverable\|ValueError when called\|No effect" docs/RIS_OPERATOR_GUIDE.md | grep -v "LLM-based\|narrative\|rejection_audit\|past_failures\|Auto-promotion\|Multi-hop" || echo "CLEAN: no stale cloud provider claims remain"</automated>
  </verify>
  <done>
    - Cloud LLM providers no longer described as "v2 deliverables" or "raise ValueError"
    - Review queue CLI documented with all 5 subcommands
    - Evaluation gate formula, routing, and priority thresholds documented
    - Retrieval benchmark command, query classes, and artifact paths documented
    - Environment variables table updated with cloud provider keys
    - Troubleshooting section updated for real provider routing behavior
    - Last verified date is 2026-04-09
  </done>
</task>

<task type="auto">
  <name>Task 2: Update README.md CLI table and RIS description, docs/README.md links, and CURRENT_STATE.md shipped-truth entries</name>
  <files>README.md, docs/README.md, docs/CURRENT_STATE.md</files>
  <action>
**README.md edits:**

1. **RIS CLI table (line ~371-389):** Add a row for `research-review` command:
   `| research-review | Operator review queue: list, inspect, accept, reject, defer pending documents |`
   Place it after the `research-health` row or grouped with other operator-facing RIS commands.

2. **"What Is Shipped Today" table (line ~49-63):** The RIS row currently says "Evaluation, ingestion, prechecking, claims extraction, scheduling, reporting, health". Update to:
   "Evaluation (weighted gate, cloud routing, fail-closed), ingestion, review queue, prechecking, claims extraction, scheduling, reporting, health/monitoring, retrieval benchmarks"

3. **RIS pre-build precheck workflow (line ~304-308):** This section is still accurate. No change needed.

4. **"What Does NOT Work Yet" in RIS_OPERATOR_GUIDE.md mentions Grafana panels:** README does not claim Grafana has RIS panels, so no change needed there.

**docs/README.md edits:**

1. The "Workflows" section (line ~52-58) already has an entry for "RIS n8n operator path" but does NOT have a direct link to the RIS_OPERATOR_GUIDE.md. Add a line:
   `- [RIS Operator Guide](RIS_OPERATOR_GUIDE.md) - Evaluation gate, review queue, ingestion, health monitoring, retrieval benchmarks`

2. In "Start here (recommended order)" (line ~6-13), add the RIS Operator Guide as item 14 if not already present:
   `14. [RIS Operator Guide](RIS_OPERATOR_GUIDE.md)`

**CURRENT_STATE.md edits:**

Append 4 new entries at the bottom of the file (after the last existing entry around line 1595) documenting the shipped Phase 2 work. Each entry should be concise and follow the existing format. Add:

1. **RIS Phase 2 -- Cloud Provider Routing (quick-260408-*, 2026-04-08)**
   - Gemini and DeepSeek HTTP clients implemented in `packages/research/evaluation/providers.py`
   - Routed evaluation: gemini (primary) -> deepseek (escalation) -> ollama (fallback)
   - Fail-closed on malformed JSON, missing fields, or provider unavailability
   - Config: `config/ris_eval_config.json` with env-var overrides (`RIS_EVAL_*`)
   - Requires `RIS_ENABLE_CLOUD_PROVIDERS=1` plus API keys
   - 120 tests passing in focused suite

2. **RIS Phase 2 -- Ingest/Review Integration (quick-260408-*, 2026-04-08)**
   - Pipeline dispositions: ACCEPT (ingest), REVIEW (pending_review queue), REJECT (clean exit), BLOCKED (scorer failure)
   - `research-review` CLI: list, inspect, accept, reject, defer
   - `pending_review` + `pending_review_history` tables in KnowledgeStore SQLite
   - Acquisition review records carry disposition, gate, pending_review_id
   - 97 tests passing in focused suite; 3779 total

3. **RIS Phase 2 -- Monitoring Truth (quick-260408-oyu, 2026-04-08)**
   - 5 new fields in RisMetricsSnapshot: provider_route_distribution, provider_failure_counts, review_queue, disposition_distribution, routing_summary
   - model_unavailable health check replaced stub with real provider failure detection
   - review_queue_backlog health check added (GREEN <= 20, YELLOW > 20, RED > 50)
   - Overall category: HEALTHY / DEGRADED / BLOCKED_ON_SETUP / FAILURE
   - 75 tests passing in monitoring suite

4. **RIS Phase 2 -- Retrieval Benchmark Truth (quick-260408-oz0, 2026-04-08)**
   - Query class segmentation: factual, analytical, exploratory
   - 8 required metrics per Phase 2 spec tracked per class per retrieval mode
   - Baseline artifacts: per_class_modes, corpus_hash, eval_config in report.json
   - Phase 2 benchmark suite: `docs/eval/ris_retrieval_benchmark.jsonl` (9 cases)
   - 35 tests passing in rag_eval suite

Keep entries concise. Follow existing entry format (section header with date/quick-id, bullet points for what shipped).
  </action>
  <verify>
    <automated>rtk grep -c "research-review" README.md docs/README.md docs/CURRENT_STATE.md docs/RIS_OPERATOR_GUIDE.md</automated>
  </verify>
  <done>
    - README.md CLI table includes research-review
    - README.md shipped table describes weighted gate, cloud routing, review queue, benchmarks
    - docs/README.md has link to RIS_OPERATOR_GUIDE.md
    - CURRENT_STATE.md has all 4 Phase 2 shipped-truth entries
  </done>
</task>

<task type="auto">
  <name>Task 3: Create dev log and run validation</name>
  <files>docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md</files>
  <action>
Create the mandatory dev log at `docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md`.

Content should include:
1. **Files changed and why** -- table listing README.md, docs/README.md, docs/RIS_OPERATOR_GUIDE.md, docs/CURRENT_STATE.md with one-line reason for each
2. **Commands run + output** -- run and record:
   - `git diff --stat -- README.md docs/README.md docs/CURRENT_STATE.md docs/RIS_OPERATOR_GUIDE.md`
   - `rg -n "research-review|pending_review|REVIEW|BLOCKED|research-health|research-stats|rag_eval|ris-unified-dev" README.md docs/README.md docs/RIS_OPERATOR_GUIDE.md docs/CURRENT_STATE.md | head -40` (verify active docs reference shipped behavior)
   - `python -m polytool --help` (CLI loads, no import errors)
   - `python -m pytest tests/ -x -q --tb=short` (no regressions; record pass/fail counts)
3. **Test results** -- exact pass/fail/skip counts from pytest
4. **Remaining active-doc caveats** -- list any items still intentionally lagging reality:
   - rejection_audit_disagreement health check remains a stub (Phase 3 / RIS v2)
   - LLM-based report synthesis remains PLANNED
   - Grafana RIS panels do not exist
   - ClickHouse RIS tables do not exist
   - SSRN / Twitter ingestion not implemented
   - past_failures in precheck always empty
   - OpenAI / Anthropic cloud providers not implemented (only Gemini + DeepSeek)
5. **Exact operator commands/doc paths updated** -- list every command example added or corrected

After creating the dev log, run the smoke test:
- `python -m polytool --help` -- verify CLI loads
- `python -m pytest tests/ -x -q --tb=short` -- verify no regressions
- `git diff --stat` -- verify only doc files changed (no code files)

Record results in the dev log.
  </action>
  <verify>
    <automated>rtk git diff --name-only | grep -v "\.md$" | grep -v "\.planning/" || echo "CLEAN: only markdown and planning files changed"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md
    - Dev log contains files changed, commands run, test results, remaining caveats
    - No code files changed (docs-only changeset)
    - Existing tests still pass
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries affected -- this is a docs-only change with no code modifications.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-jfi-01 | I (Information Disclosure) | docs/ | accept | Docs are public repo content; no secrets in any edited file. Verify no API keys or tokens appear in updated env-var documentation. |
</threat_model>

<verification>
1. `rg -n "v2 deliverable" docs/RIS_OPERATOR_GUIDE.md` returns zero matches (except for items genuinely still deferred like LLM synthesis)
2. `rg -n "research-review" README.md docs/RIS_OPERATOR_GUIDE.md` returns matches in both files
3. `rg -n "weighted.*composite\|fail-closed\|ACCEPT.*REVIEW.*REJECT" docs/RIS_OPERATOR_GUIDE.md` returns matches for the new evaluation gate section
4. `rg -n "retrieval benchmark\|query_class\|ris_retrieval_benchmark" docs/RIS_OPERATOR_GUIDE.md` returns matches for the new benchmark section
5. `git diff --name-only` shows only .md files under docs/ and README.md at root
6. `python -m pytest tests/ -x -q --tb=short` passes with no regressions
</verification>

<success_criteria>
- All 4 Phase 2 shipped behaviors (cloud routing, review integration, monitoring truth, retrieval benchmark truth) are accurately described in operator-facing docs
- No stale "v2 deliverable" or "raises ValueError" claims remain for Gemini/DeepSeek
- research-review CLI is documented in both README.md and RIS_OPERATOR_GUIDE.md
- CURRENT_STATE.md has entries for all 4 Phase 2 ships
- Zero code files changed
- Existing tests pass
- Dev log created
</success_criteria>

<output>
After completion, create `.planning/quick/260409-jfi-reconcile-repo-docs-for-shipped-phase-2-/260409-jfi-SUMMARY.md`
</output>
