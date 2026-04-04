---
phase: quick-260404-jgk
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/RIS_AUDIT_REPORT.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/dev_logs/2026-04-04_ris-audit.md
autonomous: true
requirements: [QUICK-RIS-AUDIT]

must_haves:
  truths:
    - "RIS_AUDIT_REPORT.md covers all 5 audit layers with honest IMPLEMENTED/PARTIAL/PLANNED verdicts"
    - "RIS_OPERATOR_GUIDE.md documents only what actually works, with [PLANNED] labels for unimplemented"
    - "Dev log captures audit methodology and key findings"
  artifacts:
    - path: "docs/RIS_AUDIT_REPORT.md"
      provides: "Layer-by-layer RIS compliance report"
      min_lines: 200
    - path: "docs/RIS_OPERATOR_GUIDE.md"
      provides: "Practical day-to-day RIS usage guide"
      min_lines: 100
    - path: "docs/dev_logs/2026-04-04_ris-audit.md"
      provides: "Audit session dev log"
      min_lines: 30
  key_links:
    - from: "docs/RIS_AUDIT_REPORT.md"
      to: "packages/research/"
      via: "references actual source files inspected"
      pattern: "packages/research"
    - from: "docs/RIS_OPERATOR_GUIDE.md"
      to: "CLAUDE.md RIS section"
      via: "consistent CLI examples"
      pattern: "python -m polytool research"
---

<objective>
Audit the RIS implementation against its design intent and produce an operator guide.

Purpose: Give the operator a clear-eyed view of what RIS can and cannot do today, plus
a practical guide for daily use. No code changes -- documentation only.

Output: Three files -- RIS_AUDIT_REPORT.md, RIS_OPERATOR_GUIDE.md, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md (RIS section for documented CLI commands and workflow)
@docs/CURRENT_STATE.md

Key codebase paths to inspect (read files, do NOT modify):

Layer 1 -- Ingestion:
  @packages/research/ingestion/adapters.py (adapter registry, source families)
  @packages/research/ingestion/fetchers.py (live fetchers: ArXiv, Reddit, YouTube, etc.)
  @packages/research/ingestion/pipeline.py (ingest pipeline)
  @packages/research/ingestion/extractors.py (text extractors)
  @packages/research/ingestion/claim_extractor.py (claim extraction)
  @packages/research/ingestion/seed.py (seed data)
  @packages/research/ingestion/normalize.py (normalization)
  @packages/research/ingestion/source_cache.py (source caching)
  @packages/research/ingestion/acquisition_review.py (review records)
  @packages/research/ingestion/benchmark.py (ingest benchmarks)
  @packages/research/ingestion/retriever.py (retrieval from sources)

Layer 2 -- Evaluation Gate:
  @packages/research/evaluation/evaluator.py (main eval gate)
  @packages/research/evaluation/scoring.py (4-dimension scoring)
  @packages/research/evaluation/providers.py (LLM providers)
  @packages/research/evaluation/dedup.py (deduplication)
  @packages/research/evaluation/hard_stops.py (binary pre-gate)
  @packages/research/evaluation/feature_extraction.py (deterministic features)
  @packages/research/evaluation/artifacts.py (eval artifacts)
  @packages/research/evaluation/replay.py (eval replay)
  @packages/research/evaluation/types.py (eval types)

Layer 3 -- Knowledge Store:
  @packages/polymarket/rag/knowledge_store.py (KnowledgeStore class)
  @packages/polymarket/rag/index.py (Chroma index)
  @packages/polymarket/rag/metadata.py (metadata schema)
  @packages/polymarket/rag/freshness.py (freshness decay)
  @packages/polymarket/rag/lexical.py (FTS5 lexical search)
  @packages/polymarket/rag/chunker.py (text chunking)
  @packages/polymarket/rag/embedder.py (embedding)
  @packages/polymarket/rag/query.py (query engine)
  @packages/polymarket/rag/reranker.py (cross-encoder reranking)

Layer 4 -- Synthesis:
  @packages/research/synthesis/query_planner.py (query planning)
  @packages/research/synthesis/hyde.py (HyDE generation)
  @packages/research/synthesis/retrieval.py (RAG retrieval)
  @packages/research/synthesis/report.py (report synthesizer)
  @packages/research/synthesis/precheck.py (precheck with reason codes)
  @packages/research/synthesis/precheck_ledger.py (precheck audit trail)
  @packages/research/synthesis/calibration.py (calibration)
  @packages/research/synthesis/report_ledger.py (report persistence)

Infrastructure:
  @packages/research/scheduling/scheduler.py (APScheduler integration)
  @packages/research/monitoring/health_checks.py (health)
  @packages/research/monitoring/run_log.py (run logging)
  @packages/research/monitoring/alert_sink.py (Discord alerts)
  @packages/research/metrics.py (metrics)
  @packages/research/integration/hypothesis_bridge.py (hypothesis registry bridge)
  @packages/research/integration/validation_feedback.py (validation feedback)
  @packages/research/integration/dossier_extractor.py (dossier extraction)

CLI entrypoints:
  @tools/cli/research_ingest.py
  @tools/cli/research_acquire.py
  @tools/cli/research_precheck.py
  @tools/cli/research_health.py
  @tools/cli/research_stats.py
  @tools/cli/research_report.py
  @tools/cli/research_scheduler.py
  @tools/cli/research_eval.py
  @tools/cli/research_seed.py
  @tools/cli/research_bridge.py
  @tools/cli/research_calibration.py
  @tools/cli/research_dossier_extract.py
  @tools/cli/research_extract_claims.py
  @tools/cli/research_benchmark.py

Feature docs (for cross-reference):
  @docs/features/FEATURE-ris-*.md (all RIS feature docs)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Codebase audit -- inspect all RIS layers and write RIS_AUDIT_REPORT.md</name>
  <files>docs/RIS_AUDIT_REPORT.md</files>
  <action>
Systematically read every file listed in the context section above. For each file, note:
- Whether it exists and has substantive implementation (not just stubs/pass)
- What it actually does vs what CLAUDE.md / feature docs claim
- Key classes, functions, and their completeness

Structure the audit report as follows:

```
# RIS Implementation Audit Report
Date: 2026-04-04

## Executive Summary
(overall RIS maturity: what percentage of the design is implemented, what works, what is stub/planned)

## Methodology
(list of files inspected, approach)

## Layer 1: Ingestion
### Source Adapters (adapters.py)
- ArXiv: [IMPLEMENTED/PARTIAL/PLANNED] -- details
- SSRN: [status] -- details
- Reddit: [status] -- details
- Twitter/X: [status] -- details
- YouTube: [status] -- details
- Blog/RSS: [status] -- details
- GitHub: [status] -- details
- Book/PDF: [status] -- details
- Manual URL: [status] -- details
### Live Fetchers (fetchers.py)
(what actually fetches data vs stubs)
### Pipeline (pipeline.py)
(end-to-end flow assessment)
### Text Extractors (extractors.py)
(which formats are actually extracted)
### Claim Extractor (claim_extractor.py)
(does it produce DERIVED_CLAIM objects? deterministic or LLM-based?)

## Layer 2: Evaluation Gate
### Binary Pre-Gate (hard_stops.py)
(what hard stops exist, are they wired)
### 4-Dimension Scoring (scoring.py)
(what dimensions, LLM vs deterministic)
### Deduplication (dedup.py)
(Jaccard? semantic? threshold?)
### Multi-Model Routing (providers.py)
(which providers exist, which actually work offline)
### Feature Extraction (feature_extraction.py)
(deterministic features before LLM scoring)

## Layer 3: Knowledge Store
### Chroma Collection (index.py)
(collection name, embedding model, dimensionality)
### Metadata Schema (metadata.py)
(what fields are indexed, privacy scoping)
### DERIVED_CLAIM Objects (knowledge_store.py)
(claim table schema, evidence tracking)
### Contradiction Tracking
(find_contradictions implementation status)
### Freshness Decay (freshness.py)
(decay function, half-life values)

## Layer 4: Synthesis
### Query Planner (query_planner.py)
(what it does, single vs multi-hop)
### HyDE (hyde.py)
(hypothetical document embedding, provider dependency)
### RAG Retrieval (retrieval.py)
(hybrid search, RRF, reranking)
### Report Synthesizer (report.py)
(report generation, template, LLM dependency)
### Precheck (precheck.py)
(reason codes: GO/CAUTION/STOP, wiring)
### Override Artifacts
(precheck_ledger.py -- what is tracked)

## Infrastructure
### APScheduler (scheduler.py)
(JOB_REGISTRY, job definitions, actual schedule)
### CLI Commands
(table of all research-* CLIs with working/broken/stub status)
### Grafana Panels
(any evidence of Grafana integration)
### ClickHouse Tables
(any evidence of CH research tables)
### Discord Alerts (alert_sink.py)
(wired to scheduler? manual only?)

## Cross-Cutting Concerns
### Offline-First Compliance
(which components require network/LLM and which are truly offline)
### Test Coverage
(count of test files matching test_research* or test_ris* or test_rag*)

## Gap Summary Table
| Component | Status | Notes |
|-----------|--------|-------|
(one row per component with IMPLEMENTED/PARTIAL/PLANNED)
```

Be honest. If something is a stub that returns a hardcoded value, say so. If something
works well, say so. The operator needs ground truth, not optimism.

Do NOT modify any source code. This is a read-only audit.
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/RIS_AUDIT_REPORT.md" && wc -l "D:/Coding Projects/Polymarket/PolyTool/docs/RIS_AUDIT_REPORT.md" | awk '{if ($1 >= 200) print "PASS: "$1" lines"; else print "FAIL: only "$1" lines"}'</automated>
  </verify>
  <done>RIS_AUDIT_REPORT.md exists with 200+ lines covering all 5 audit layers, each component has an honest IMPLEMENTED/PARTIAL/PLANNED verdict, gap summary table at the end</done>
</task>

<task type="auto">
  <name>Task 2: Write RIS_OPERATOR_GUIDE.md based on audit findings</name>
  <files>docs/RIS_OPERATOR_GUIDE.md</files>
  <action>
Using the findings from Task 1, create a practical operator guide. This is NOT a design
doc -- it is a "how to use what exists today" guide.

Structure:

```
# RIS Operator Guide
Last verified: 2026-04-04

## Quick Reference
(table of CLI commands that actually work, with one-liner descriptions)

## Daily Workflows

### Ingesting Research
(step-by-step for each working source type)
#### From a URL (academic paper, blog post, GitHub repo)
#### From manual text (AI chat session findings)
#### From a file (notes, exported doc)
#### From ArXiv topic search
#### From Reddit
#### From YouTube

### Querying the Knowledge Store
#### Simple RAG query
#### Hybrid search (semantic + lexical)
#### With reranking

### Running Precheck Before Implementation
(exact commands, interpreting GO/CAUTION/STOP)

### Generating Research Reports
(if implemented -- otherwise mark [PLANNED])

### Health Monitoring
#### research-health
#### research-stats
#### research-scheduler status

## Scheduler Setup
(how to start/stop the scheduler, what jobs run, caveats)

## Advanced Workflows

### Dossier Extraction
(extracting research from wallet dossiers)

### SimTrader Bridge
(registering hypotheses from research, recording validation outcomes)

### Claim Extraction
(extracting structured claims from ingested documents)

### Calibration
(if implemented)

## What Does NOT Work Yet [PLANNED]
(honest list of things documented in specs/roadmap but not implemented)
- Twitter/X ingestion
- SSRN adapter
- Cloud LLM providers for evaluation
- (etc. -- based on audit findings)

## Troubleshooting
### Common errors and fixes
### Environment variables needed
### Optional dependencies (praw, yt-dlp, pdfplumber, python-docx)

## File Layout Reference
(where RIS files live in the repo)
```

Mark EVERY unimplemented feature with [PLANNED]. Never describe planned features as
if they work. The operator should be able to follow this guide and have everything
succeed on the first try.

Cross-reference with CLAUDE.md RIS section -- the guide should be consistent with
the CLI examples documented there, and flag any discrepancies found during the audit.
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/RIS_OPERATOR_GUIDE.md" && wc -l "D:/Coding Projects/Polymarket/PolyTool/docs/RIS_OPERATOR_GUIDE.md" | awk '{if ($1 >= 100) print "PASS: "$1" lines"; else print "FAIL: only "$1" lines"}'</automated>
  </verify>
  <done>RIS_OPERATOR_GUIDE.md exists with 100+ lines, every command example is verified against actual CLI code, unimplemented features are labeled [PLANNED], operator can follow guide without hitting unimplemented stubs</done>
</task>

<task type="auto">
  <name>Task 3: Write dev log</name>
  <files>docs/dev_logs/2026-04-04_ris-audit.md</files>
  <action>
Write a dev log capturing:
- What was audited (RIS layers 1-4 + infrastructure)
- Methodology (read-only codebase inspection, no code changes)
- Key findings summary (what percentage implemented, biggest gaps, surprises)
- Files inspected count
- Test count for RIS-related tests (run: `python -m pytest tests/ -k "research or ris or rag or precheck or knowledge" --collect-only -q 2>/dev/null | tail -5` to get count)
- Any discrepancies found between CLAUDE.md and actual implementation
- Artifacts produced (the two docs)
- Open questions or recommendations for the operator

Follow the standard dev log format:
```
# Dev Log: RIS Implementation Audit
Date: 2026-04-04
Task: quick-260404-jgk

## Objective
...
## Methodology
...
## Key Findings
...
## Artifacts Produced
...
## Open Questions
...
```
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-04_ris-audit.md" && wc -l "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-04_ris-audit.md" | awk '{if ($1 >= 30) print "PASS: "$1" lines"; else print "FAIL: only "$1" lines"}'</automated>
  </verify>
  <done>Dev log exists with 30+ lines, captures methodology, key findings, and open questions</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply -- this is a read-only documentation task. No code is modified,
no external services are contacted, no secrets are handled.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | I (Information Disclosure) | Audit report | accept | Report may reference file paths and function names but contains no secrets, API keys, or credentials. Review before sharing externally. |
</threat_model>

<verification>
All three files exist and meet minimum line counts:
- docs/RIS_AUDIT_REPORT.md (200+ lines)
- docs/RIS_OPERATOR_GUIDE.md (100+ lines)
- docs/dev_logs/2026-04-04_ris-audit.md (30+ lines)

No source code was modified (git diff should show only new files under docs/).
</verification>

<success_criteria>
1. RIS_AUDIT_REPORT.md covers all 5 audit layers with per-component verdicts
2. RIS_OPERATOR_GUIDE.md contains only working commands, [PLANNED] for the rest
3. Dev log captures methodology and findings
4. No source code modifications -- documentation only
5. Gap summary table in audit report gives operator clear view of RIS maturity
</success_criteria>

<output>
After completion, create `.planning/quick/260404-jgk-ris-implementation-audit-operator-guide/260404-jgk-SUMMARY.md`
</output>
