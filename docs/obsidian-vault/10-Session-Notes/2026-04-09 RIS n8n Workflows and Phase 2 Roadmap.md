---
tags: [session-note]
date: 2026-04-09
status: active
topics: [ris, n8n, evaluation-gate, monitoring, phase-2]
---
# RIS n8n Workflows & Phase 2 Roadmap Session

## What Happened

Extended session covering n8n workflow design, implementation, iteration, and Phase 2 roadmap creation for the Research Intelligence System.

## Key Outcomes

### n8n Workflow System — Built and Deployed
- **Architecture decision:** Sub-workflow pattern (7 pipelines + 1 orchestrator) for production, unified single workflow for development/iteration.
- **MCP connection issues:** Instance-level MCP couldn't connect from Claude Code. Resolved by using n8n REST API via curl instead (n8n-mcp kept for documentation only, no API credentials).
- **Three build iterations:**
  1. First build: skeletal (trigger → command, no error handling)
  2. Second build: added error handling, Discord alerts, metrics parsing (separate workflows)
  3. Third build: unified single development workflow with all 9 sections on one canvas
- **Current state:** Unified workflow `RIS — Research Intelligence System` deployed with ~87 nodes across 9 sections. Architect subsequently migrated workflows to `infra/n8n/workflows/` per ADR 0013.
- **n8n REST API pattern:** `N8N_API_KEY` in `.env`, Claude Code uses curl for all workflow CRUD. Works reliably.

### Phase 2 Roadmap — Created and Architect-Reviewed
Four priorities identified:
1. **Wire cloud LLM evaluation providers** (Gemini Flash primary, DeepSeek V3 escalation, Ollama fallback) — model swappability via `OpenAICompatibleProvider` base class
2. **ClickHouse metrics pipeline + Grafana dashboard** — n8n execution data → ClickHouse → 4-panel dashboard
3. **RAG retrieval quality testing** — golden test set, benchmark script, A/B testing retrieval strategies
4. **n8n workflow improvements** — execution summaries, rich Discord embeds, variables, analytics

### Architect Review — 11 Points Accepted
All architect feedback incorporated:
- Fail-closed contract (no silent auto-accept on provider failure)
- Weighted composite + per-dimension floor as gate (simple sum as diagnostic)
- Review queue specification (pending_review table, CLI, accept/reject persistence)
- Budget control (global 1500/day Gemini cap, per-source ceilings, manual reserve)
- Storage-level idempotency for metrics (ReplacingMergeTree + code-level prefilter)
- Segmented benchmark metrics by query class
- Novelty dedup protection (canonical doc ID before neighbor injection)
- n8n env-var fallback as primary design (Variables as convenience)
- Acceptance criteria per priority with concrete pass/fail checks
- Research-only posture statement
- PLAN_OF_RECORD.md reconciliation before implementation

### Architect Claims Phase 2 Complete
Per `02-Modules/RIS.md`, Phase 2 capabilities listed as shipped:
- Weighted composite evaluation gate (fail-closed, per-priority thresholds)
- Cloud provider routing: Gemini primary, DeepSeek escalation, Ollama fallback
- Ingest/review integration: ACCEPT/REVIEW/REJECT/BLOCKED dispositions
- Monitoring: provider failure detection, review queue backlog, 7 health checks
- Retrieval benchmark: query class segmentation, per-class metrics, baseline artifacts
- Discord embed alerting via n8n

**Status: UNVERIFIED.** Need codebase audit to confirm these claims.

## Research Reports Generated (4)
1. Gemini 2.5 Flash structured evaluation — complete Python implementation
2. n8n advanced patterns — execution summaries, rich Discord embeds, rate limiting
3. RAG retrieval quality testing — golden test set, IR metrics, A/B testing
4. n8n execution data → ClickHouse + Grafana — workflow JSON, DDL, dashboard JSON

## Open Items
- [ ] Verify architect's Phase 2 completion claims via codebase audit
- [ ] Run Phase R0 seed (17 foundational documents)
- [ ] Test Gemini Flash provider end-to-end
- [ ] Test n8n unified workflow execution
- [ ] Create golden test set for RAG benchmark
- [ ] Import Grafana dashboard JSON

## Cross-References
- [[02-Modules/RIS]] — Module inventory (claims Phase 2 shipped)
- [[09-Decisions/Decision - RIS n8n Pilot Scope]] — ADR 0013
- [[08-Research/06-Wallet-Discovery-Roadmap]] — Similar architect review pattern
